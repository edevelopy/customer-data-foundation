import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest

from fde_foundation.importer import ensure_schema, import_csv


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    ensure_schema(url)
    with psycopg.connect(url) as connection:
        connection.execute("TRUNCATE TABLE customers, import_batches RESTART IDENTITY CASCADE;")
    return url


def write_csv(path: Path, rows: str) -> Path:
    path.write_text(
        "email,first_name,last_name,phone,source\n" + rows,
        encoding="utf-8",
    )
    return path


@pytest.mark.integration
def test_import_and_exact_reimport_are_idempotent(tmp_path: Path, database_url: str) -> None:
    csv_path = write_csv(
        tmp_path / "customers.csv",
        "alice@example.com,Alice,Rivera,+14075550101,partner\n"
        "bob@example.com,Bob,Smith,,internal\n",
    )

    first = import_csv(csv_path, database_url)
    second = import_csv(csv_path, database_url)

    assert first.accepted is True
    assert first.status == "imported"
    assert first.inserted_rows == 2
    assert second.accepted is True
    assert second.status == "already_imported"
    assert second.inserted_rows == 0
    assert second.existing_rows == 2
    with psycopg.connect(database_url) as connection:
        customer_count = connection.execute("SELECT count(*) FROM customers;").fetchone()
        batch_count = connection.execute("SELECT count(*) FROM import_batches;").fetchone()
    assert customer_count == (2,)
    assert batch_count == (1,)


@pytest.mark.integration
def test_concurrent_exact_import_creates_one_batch(tmp_path: Path, database_url: str) -> None:
    csv_path = write_csv(
        tmp_path / "customers.csv",
        "alice@example.com,Alice,Rivera,+14075550101,partner\n"
        "bob@example.com,Bob,Smith,,internal\n",
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: import_csv(csv_path, database_url), range(2)))

    assert sorted(result.status for result in results) == ["already_imported", "imported"]
    with psycopg.connect(database_url) as connection:
        customer_count = connection.execute("SELECT count(*) FROM customers;").fetchone()
        batch_count = connection.execute("SELECT count(*) FROM import_batches;").fetchone()
    assert customer_count == (2,)
    assert batch_count == (1,)


@pytest.mark.integration
def test_same_normalized_customer_is_safe_across_different_files(
    tmp_path: Path, database_url: str
) -> None:
    first_path = write_csv(
        tmp_path / "first.csv",
        "alice@example.com,Alice,Rivera,+14075550101,partner\n",
    )
    second_path = write_csv(
        tmp_path / "second.csv",
        " ALICE@example.com ,Alice,Rivera,+14075550101,partner\n",
    )

    first = import_csv(first_path, database_url)
    second = import_csv(second_path, database_url)

    assert first.status == "imported"
    assert second.status == "imported"
    assert second.inserted_rows == 0
    assert second.existing_rows == 1
    with psycopg.connect(database_url) as connection:
        customer_count = connection.execute("SELECT count(*) FROM customers;").fetchone()
        batch_count = connection.execute("SELECT count(*) FROM import_batches;").fetchone()
    assert customer_count == (1,)
    assert batch_count == (2,)


@pytest.mark.integration
def test_conflict_rolls_back_new_customers_and_batch(tmp_path: Path, database_url: str) -> None:
    original_path = write_csv(
        tmp_path / "original.csv",
        "alice@example.com,Alice,Rivera,+14075550101,partner\n",
    )
    conflicting_path = write_csv(
        tmp_path / "conflicting.csv",
        "bob@example.com,Bob,Smith,+14075550102,internal\n"
        "alice@example.com,Alice,Rivera,+14075550999,partner\n",
    )
    assert import_csv(original_path, database_url).accepted is True

    result = import_csv(conflicting_path, database_url)

    assert result.accepted is False
    assert result.status == "conflict"
    assert result.issues[0].code == "customer_conflict"
    assert result.issues[0].row == 3
    with psycopg.connect(database_url) as connection:
        customers = connection.execute(
            "SELECT first_name, last_name, phone, source FROM customers ORDER BY email;"
        ).fetchall()
        batch_count = connection.execute("SELECT count(*) FROM import_batches;").fetchone()
    assert customers == [("Alice", "Rivera", "+14075550101", "partner")]
    assert batch_count == (1,)
