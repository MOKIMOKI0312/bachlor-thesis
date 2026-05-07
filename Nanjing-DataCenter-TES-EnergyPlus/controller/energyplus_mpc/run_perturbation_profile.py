"""Run a short TES_Set perturbation profile through EnergyPlus."""

from __future__ import annotations

import sys

from .run_energyplus_mpc import main as run_main


def main(argv: list[str] | None = None) -> int:
    args = ["--controller", "perturbation"]
    args.extend(sys.argv[1:] if argv is None else argv)
    return run_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
