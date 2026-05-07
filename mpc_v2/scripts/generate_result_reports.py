"""Deprecated advanced report generator for the pre-rebuild MPC matrix."""

from __future__ import annotations

import argparse

from mpc_v2.core.io_schemas import UnsupportedFeatureError


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    raise UnsupportedFeatureError(
        "advanced attribution/result reports are deferred after the MPC v1 rebuild; "
        "read summary.csv or validation_summary.csv directly."
    )


if __name__ == "__main__":
    raise SystemExit(main())
