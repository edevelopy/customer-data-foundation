"""Export the deterministic FastAPI contract as a versioned client artifact."""

from __future__ import annotations

import json
from pathlib import Path

from fde_foundation.api import app


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    destination = project_root / "docs" / "openapi.json"
    destination.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(destination)


if __name__ == "__main__":
    main()
