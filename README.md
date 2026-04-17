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
8. **Version-gated `<variable id>` tokens** — well-known ids (e.g. `oasis_codes_id` / `clients_code_id`, `call_oasis_enddef`) warn when used under the wrong `--xios-version`, with a rename hint pointing at the replacement.

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

Files with `.xml.j2` extension are automatically preprocessed:
- `{{ expression }}` is replaced with a safe placeholder
- `{% block %}` statements are stripped
- `{# comments #}` are stripped

This allows structural validation of Jinja2 templates used by tools like [esm-tools](https://github.com/esm-tools/esm_tools).

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
