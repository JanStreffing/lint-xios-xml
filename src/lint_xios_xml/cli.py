"""Command-line interface for the XIOS XML linter."""

import argparse
import sys

from lint_xios_xml.linter import XiosLinter, collect_files
from lint_xios_xml.schemas import DEFAULT_VERSION, list_versions


# Default ``xios.version`` string seeded into the Jinja2 render context
# when ``--xios-version`` is passed but the user did not explicitly set
# ``xios.version`` via ``--define``. Using concrete release strings
# (``"2.5"``, ``"3.0"``) so template predicates like
# ``xios.version.startswith("3")`` resolve as expected.
_DEFAULT_XIOS_VERSION_STRING = {"2": "2.5", "3": "3.0"}


def _set_nested(target, dotted_key, value):
    """Set ``target[a][b][c] = value`` for a dotted key ``a.b.c``.

    Intermediate keys that aren't dicts are overwritten — we assume the
    user owns their own ``--define`` namespace.
    """
    parts = dotted_key.split(".")
    node = target
    for part in parts[:-1]:
        if not isinstance(node.get(part), dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value


def _parse_defines(define_args):
    """Turn a list of ``key.sub=value`` strings into a nested dict."""
    out = {}
    for entry in define_args:
        if "=" not in entry:
            raise SystemExit(
                f"--define expects KEY=VALUE (got {entry!r})"
            )
        key, value = entry.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit(f"--define has empty key in {entry!r}")
        _set_nested(out, key, value)
    return out


def main():
    versions = list_versions()
    parser = argparse.ArgumentParser(
        description="XIOS XML Linter — validates XIOS configuration files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s core_atm/
  %(prog)s core_atm/ --alternatives "field_def.xml,field_def_cmip6.xml,field_def_cmip7.xml"
  %(prog)s --all
  %(prog)s --xios-version 3 core_atm/
  %(prog)s --xios-version 3 --define xios.version=3.0 iodef.xml.j2""",
    )
    parser.add_argument("paths", nargs="*", default=["."], help="Files or directories to lint")
    parser.add_argument("--all", action="store_true", help="Lint all .xml/.xml.j2 in current directory tree")
    parser.add_argument(
        "--xios-version", default=DEFAULT_VERSION,
        choices=versions,
        help=f"XIOS version to validate against (default: {DEFAULT_VERSION})",
    )
    parser.add_argument(
        "--alternatives", action="append", default=[],
        metavar="FILE1,FILE2,...",
        help="Comma-separated group of filenames that are alternatives "
             "(only one active at runtime). Duplicate ids between them "
             "are suppressed. Can be repeated for multiple groups.",
    )
    parser.add_argument(
        "--define", action="append", default=[],
        metavar="KEY=VALUE",
        help="Set a Jinja2 variable used to render .xml.j2 templates. "
             "Dotted keys build nested dicts (e.g. --define "
             "xios.version=3.0 makes {{ xios.version }} render as '3.0' "
             "and {% if xios.version.startswith('3') %} pick the XIOS 3 "
             "branch). Can be repeated.",
    )
    args = parser.parse_args()

    if args.all:
        files = collect_files(["."])
    else:
        files = collect_files(args.paths)

    if not files:
        print("No XML files found.")
        return 0

    alt_groups = []
    for group_str in args.alternatives:
        alt_groups.append([f.strip() for f in group_str.split(",")])

    jinja_vars = _parse_defines(args.define)
    # Auto-seed ``xios.version`` from --xios-version unless the user
    # already provided one via --define.
    xios_ns = jinja_vars.get("xios") if isinstance(jinja_vars.get("xios"), dict) else None
    if (
        args.xios_version in _DEFAULT_XIOS_VERSION_STRING
        and not (xios_ns and "version" in xios_ns)
    ):
        _set_nested(
            jinja_vars, "xios.version",
            _DEFAULT_XIOS_VERSION_STRING[args.xios_version],
        )

    linter = XiosLinter(
        alternative_groups=alt_groups,
        xios_version=args.xios_version,
        jinja_vars=jinja_vars or None,
    )
    print(f"Linting {len(files)} file(s) with XIOS {args.xios_version} schema...")
    for f in files:
        print(f"  {f}")
        linter.lint_file(str(f))

    linter.check_refs()

    print()
    return linter.report()


if __name__ == "__main__":
    sys.exit(main())
