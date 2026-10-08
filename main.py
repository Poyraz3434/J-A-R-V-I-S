"""J.A.R.V.I.S. application entry point."""

import sys


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        from services.packaging_validation import frozen_runtime_check

        raise SystemExit(0 if frozen_runtime_check() else 1)
    from jarvis_v10 import main

    main()
