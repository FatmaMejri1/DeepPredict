#!/usr/bin/env python
"""Fail-closed entry point for the complete guarded Django test suite."""

import os
import sys
import uuid
from pathlib import Path


VALUE_OPTIONS = {"--verbosity"}
FLAG_OPTIONS = {
    "--noinput",
    "--no-input",
    "--failfast",
    "--no-color",
    "--force-color",
    "--traceback",
}


def _validate_arguments(arguments):
    if not arguments or arguments[0] != "test":
        raise SystemExit("Use full_regression_manage.py test with no test labels.")

    index = 1
    while index < len(arguments):
        token = arguments[index]
        option, separator, value = token.partition("=")
        if option in FLAG_OPTIONS:
            if separator:
                raise SystemExit(f"Option {option} does not accept a value.")
        elif option in VALUE_OPTIONS:
            if not separator:
                index += 1
                if index >= len(arguments) or arguments[index].startswith("-"):
                    raise SystemExit(f"Option {option} requires a value.")
                value = arguments[index]
            if option == "--verbosity" and value not in {"0", "1", "2", "3"}:
                raise SystemExit("--verbosity must be 0, 1, 2, or 3.")
        else:
            raise SystemExit(f"Unrecognized or disallowed test option/label: {token}")
        index += 1


def main():
    _validate_arguments(sys.argv[1:])

    # Configure all selectors before Django or its connection handler is imported.
    owner = uuid.uuid4().hex
    if len(owner) != 32 or any(character not in "0123456789abcdef" for character in owner):
        raise SystemExit("Could not generate a valid isolated run owner.")
    os.environ["DB_ENGINE"] = "sqlite"
    os.environ["DEEPPREDICT_FULL_REGRESSION_OWNER"] = owner
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.full_regression_settings"
    backend_directory = Path(__file__).resolve(strict=True).parent
    os.environ["DEEPPREDICT_E2E_EVIDENCE_DIR"] = str(
        backend_directory / "evidence" / "e2e" / f"full-regression-{owner}"
    )

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
