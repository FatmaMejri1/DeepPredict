"""Bootstrap only the Angular browser E2E tests with isolated settings."""

import os
import re
import sys


E2E_LABEL_PATTERN = re.compile(r"^dashboard\.test_e2e(?:\.[A-Za-z_]\w*)*$")

FLAG_OPTIONS = {
    "--noinput",
    "--no-input",
    "--failfast",
    "--keepdb",
    "--reverse",
    "--debug-mode",
    "--debug-sql",
    "--pdb",
    "--buffer",
    "--timing",
    "--no-faulthandler",
    "-r",
    "-d",
    "-b",
    "--no-color",
    "--force-color",
    "--skip-checks",
    "--traceback",
}
VALUE_OPTIONS = {
    "--verbosity",
    "--tag",
    "--exclude-tag",
    "--pattern",
    "--top-level-directory",
    "--durations",
    "-v",
    "-k",
    "-p",
    "-t",
}


def _validate_arguments(arguments):
    if not arguments or arguments[0] != "test":
        raise SystemExit("Use e2e_manage.py test with dashboard.test_e2e labels only.")

    labels = []
    index = 1
    while index < len(arguments):
        token = arguments[index]
        if token.startswith("--") or token in FLAG_OPTIONS or token in VALUE_OPTIONS:
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
                if option == "--durations":
                    try:
                        if int(value) < 0:
                            raise ValueError
                    except ValueError:
                        raise SystemExit("--durations must be a non-negative integer.")
            elif option == "--parallel":
                if separator:
                    parallel_value = value
                elif index + 1 < len(arguments) and arguments[index + 1] in {"auto"}:
                    index += 1
                    parallel_value = arguments[index]
                elif index + 1 < len(arguments):
                    try:
                        int(arguments[index + 1])
                    except ValueError:
                        parallel_value = "auto"
                    else:
                        index += 1
                        parallel_value = arguments[index]
                else:
                    parallel_value = "auto"
                if parallel_value != "auto":
                    try:
                        if int(parallel_value) < 1:
                            raise ValueError
                    except ValueError:
                        raise SystemExit("--parallel must be auto or a positive integer.")
            elif option == "--shuffle":
                # Django accepts a bare --shuffle or an explicit integer seed.
                if separator:
                    seed = value
                elif index + 1 < len(arguments):
                    try:
                        int(arguments[index + 1])
                    except ValueError:
                        seed = None
                    else:
                        index += 1
                        seed = arguments[index]
                else:
                    seed = None
                if seed is not None:
                    try:
                        int(seed)
                    except ValueError:
                        raise SystemExit("--shuffle seed must be an integer.")
            else:
                raise SystemExit(f"Unrecognized or disallowed Django test option: {option}")
        elif token.startswith("-"):
            raise SystemExit(f"Unrecognized positional argument: {token}")
        else:
            labels.append(token)
        index += 1

    if not labels:
        raise SystemExit("At least one dashboard.test_e2e test label is required.")
    if any(E2E_LABEL_PATTERN.fullmatch(label) is None for label in labels):
        raise SystemExit("Every test label must target dashboard.test_e2e only.")


def main():
    _validate_arguments(sys.argv[1:])

    # These assignments must happen before importing Django's management layer.
    os.environ["DB_ENGINE"] = "sqlite"
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.e2e_settings"

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
