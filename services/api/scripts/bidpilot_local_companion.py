"""Compatibility wrapper for the installed local companion command.

Prefer ``bidpilot-local-companion`` after installing the API package. This
script remains so existing development instructions continue to work.
"""

from app.runtime.local_companion_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
