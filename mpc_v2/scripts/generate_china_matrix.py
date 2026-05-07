"""Deprecated China TOU/DR matrix generator.

The MPC rebuild intentionally removes the old large matrix implementation.
Use mpc_v2/scripts/run_validation_matrix.py for the rebuilt v1 smoke matrix.
"""

from __future__ import annotations

import argparse

from mpc_v2.core.io_schemas import UnsupportedFeatureError


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    raise UnsupportedFeatureError(
        "China TOU/DR matrix generation is deferred after the MPC v1 rebuild; "
        "use mpc_v2/config/scenario_sets.yaml for the minimal validation matrix."
    )


if __name__ == "__main__":
    raise SystemExit(main())
