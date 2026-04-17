# lint-xios-xml

A linter for [XIOS](https://forge.ipsl.jussieu.fr/ioserver) XML configuration files, with Jinja2 template support.

Catches common configuration mistakes before they cause cryptic runtime failures in your Earth System Model.

## Checks

1. **Well-formed XML** (with Jinja2 `{{ }}`, `{% %}`, `{# #}` preprocessing)
2. **Known XIOS elements** (field, file, grid, domain, axis, variable, transformations, ...)
3. **Known attributes** per element type
4. **Reference integrity** (`field_ref`, `grid_ref`, `domain_ref`, `axis_ref`, `scalar_ref` resolve to existing `id`s)
5. **Required attributes** (e.g. `<field>` in `field_definition` should have `id`)
6. **Enum validation** (`operation`, `type`, `format`, `par_access`, `timeseries`, `positive`, ...)
7. **Duplicate id detection** (with support for alternative file sets)

## Installation

```bash
pip install git+https://github.com/JanStreffing/lint-xios-xml.git
```

Or for development:
```bash
git clone https://github.com/JanStreffing/lint-xios-xml.git
cd lint-xios-xml
pip install -e ".[dev]"
```

## Usage

```bash
# Lint a directory of XIOS XML files
lint-xios-xml core_atm/

# Lint specific files
lint-xios-xml field_def_cmip7.xml file_def.xml.j2

# Lint everything under current directory
lint-xios-xml --all
```

### Alternative file sets

XIOS setups often include multiple variants of the same file (e.g. `field_def.xml`, `field_def_cmip6.xml`, `field_def_cmip7.xml`) where only one is active at runtime. Use `--alternatives` to suppress false-positive duplicate-id errors between them:

```bash
lint-xios-xml core_atm/ \
    --alternatives "field_def.xml,field_def_cmip6.xml,field_def_cmip7.xml,field_def_lpjg_safe.xml" \
    --alternatives "file_def.xml.j2,file_def_lpjg_spinup.xml.j2,file_def_oifs_cmip7_spinup.xml.j2"
```

Each file in the group is still fully linted individually for structure, enums, and attributes. Only cross-file duplicate-id checks are suppressed within a group.

### Jinja2 templates

Files with `.xml.j2` extension are automatically preprocessed. There are two modes:

**Without `--define`** (default, lightweight):
- `{{ expression }}` is replaced with a safe placeholder
- `{% block %}` statements are stripped — both branches of an `{% if %}/{% else %}` remain
- `{# comments #}` are stripped

**With `--define KEY=VALUE`** (full Jinja2 render):
- The template is rendered with the provided variables; conditional blocks collapse to the matching branch.
- Dotted keys build nested dicts: `--define xios.version=3.0` makes `{{ xios.version }}` render as `3.0` and `{% if xios.version.startswith("3") %}` pick the XIOS 3 branch.
- Undefined names (e.g. `{{ unknown.thing }}`) resolve to the placeholder instead of crashing the template.
- `--xios-version 2` / `--xios-version 3` auto-seed `xios.version` to `"2.5"` / `"3.0"` unless overridden by an explicit `--define xios.version=…`.

This is what makes version-unified `iodef.xml.j2` files lint cleanly under a specific XIOS version.

Example:
```bash
# Lint a unified multi-version iodef template as XIOS 3
lint-xios-xml --xios-version 3 --define xios.version=3.0 iodef.xml.j2
```

### `src=` inclusions

When XIOS includes a file via `<context id="oifs" src="./context_ifs.xml"/>`, the id appears both in the including file and the included file. The linter recognizes `src=` as an inclusion pointer and does not flag this as a duplicate.

## Python API

```python
from lint_xios_xml import XiosLinter

linter = XiosLinter(alternative_groups=[["field_def.xml", "field_def_cmip7.xml"]])
linter.lint_file("field_def.xml")
linter.lint_file("field_def_cmip7.xml")
linter.lint_file("file_def.xml.j2")
linter.check_refs()
exit_code = linter.report()
```

## License

MIT
