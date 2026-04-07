"""Command-line interface for the XIOS XML linter."""

import argparse
import sys

from lint_xios_xml.linter import XiosLinter, collect_files
from lint_xios_xml.schemas import DEFAULT_VERSION, list_versions


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
  %(prog)s --xios-version 3 core_atm/""",
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

    linter = XiosLinter(
        alternative_groups=alt_groups,
        xios_version=args.xios_version,
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
