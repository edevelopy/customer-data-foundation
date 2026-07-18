"""Preflight seguro de configuracion para API, worker y partner."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable

from fde_foundation.integration_worker import WorkerSettings
from fde_foundation.partner_api import PartnerSettings
from fde_foundation.settings import ConfigurationError, Settings

LOADERS: dict[str, Callable[[], object]] = {
    "api": Settings.from_environment,
    "worker": WorkerSettings.from_environment,
    "partner": PartnerSettings.from_environment,
}


def validate_targets(targets: list[str]) -> dict[str, object]:
    try:
        for target in targets:
            LOADERS[target]()
    except ConfigurationError:
        return {"code": "configuration_invalid", "status": "invalid", "targets": targets}
    return {"status": "ready", "targets": targets}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "targets",
        nargs="+",
        choices=tuple(LOADERS),
        help="componentes cuya configuracion se validara",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_targets(args.targets)
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return int(result["status"] != "ready")


if __name__ == "__main__":
    raise SystemExit(main())
