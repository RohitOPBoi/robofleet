"""Allow running robofleet.cli directly as `python -m robofleet.cli`."""

from robofleet.cli.main import main

if __name__ == "__main__":
    import sys

    sys.exit(main())
