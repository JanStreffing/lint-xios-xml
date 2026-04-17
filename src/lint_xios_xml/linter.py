"""Core linter logic for XIOS XML configuration files.

Checks performed:
  1. Well-formed XML (with Jinja2 template support)
  2. Known XIOS element names
  3. Known attributes per element type
  4. Reference integrity (*_ref attributes resolve to existing ids)
  5. Required attributes per element type
  6. Enum value validation (operation, type, format, etc.)
  7. Duplicate id detection
"""

import fnmatch
import re
from pathlib import Path

from lxml import etree

from lint_xios_xml.schemas import DEFAULT_VERSION, get_schema


# Placeholder string substituted for template expressions that cannot be
# resolved to a concrete value. Kept identical to the pre-Jinja2-rendering
# behavior so downstream checks that look for this marker keep working.
_JINJA_PLACEHOLDER = "JINJA_PLACEHOLDER"


class _SilentUndefined:
    """Stand-in returned for every undefined name / attribute access.

    Renders to the linter's ``JINJA_PLACEHOLDER`` sentinel, supports any
    attribute access (``foo.bar.baz``) and indexing (``foo[0]``), is
    callable (so ``{{ x.startswith('3') }}`` in an ``{% if %}`` returns a
    truthy placeholder), and evaluates as falsy in boolean context so
    branches guarded by ``{% if undefined %}`` are skipped rather than
    crashing the template.
    """

    def __getattr__(self, _name):  # any attribute path resolves to self
        return self

    def __getitem__(self, _key):
        return self

    def __call__(self, *_args, **_kwargs):
        # String methods like .startswith() return a string; other calls
        # stay as the placeholder object.
        return self

    def __bool__(self):
        return False

    def __iter__(self):
        return iter(())

    def __str__(self):
        return _JINJA_PLACEHOLDER

    def __repr__(self):
        return _JINJA_PLACEHOLDER


def preprocess_jinja(text, variables=None):
    """Prepare a Jinja2 template for XML parsing.

    Two modes:

    * **No ``variables``** (default): legacy regex-based stripping is used.
      ``{{ expr }}`` → ``JINJA_PLACEHOLDER``, ``{% block %}`` and
      ``{# comment #}`` are removed. Both branches of an ``{% if %}`` end
      up in the output.
    * **``variables`` given**: a real Jinja2 ``Environment`` renders the
      template with that context. Conditional blocks collapse to the
      branch that matches the provided variables. Undefined names are
      caught by a permissive ``Undefined`` subclass that stringifies to
      ``JINJA_PLACEHOLDER`` instead of crashing, so templates with
      unresolved ``{{ foo.bar }}`` still lint.
    """
    if not variables:
        text = re.sub(r"\{\{[^}]*\}\}", _JINJA_PLACEHOLDER, text)
        text = re.sub(r"\{%[^%]*%\}", "", text)
        text = re.sub(r"\{#[^#]*#\}", "", text)
        return text

    # Lazy import: Jinja2 is a runtime dep, but unused code paths
    # shouldn't pay for it.
    from jinja2 import Environment, Undefined

    class _PermissiveUndefined(Undefined):
        """Jinja2 ``Undefined`` that silently stringifies to the
        placeholder and is falsy / iterable-empty. Attribute access and
        indexing return another instance instead of raising, so
        ``{{ a.b.c }}`` works even when ``a`` is undefined.
        """

        __slots__ = ()

        def __getattr__(self, _name):
            return self.__class__()

        def __getitem__(self, _key):
            return self.__class__()

        def __call__(self, *_args, **_kwargs):
            return self.__class__()

        def __bool__(self):
            return False

        def __iter__(self):
            return iter(())

        def __str__(self):
            return _JINJA_PLACEHOLDER

        def __repr__(self):
            return _JINJA_PLACEHOLDER

    env = Environment(
        undefined=_PermissiveUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    template = env.from_string(text)
    return template.render(**variables)


def collect_files(paths):
    """Expand directories and globs into a list of XML/XML.j2 files."""
    import sys

    result = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            result.extend(sorted(path.glob("**/*.xml")))
            result.extend(sorted(path.glob("**/*.xml.j2")))
        elif path.exists():
            result.append(path)
        else:
            print(f"WARNING: {p} not found, skipping", file=sys.stderr)
    return result


class XiosLinter:
    """XIOS XML configuration linter.

    Parameters
    ----------
    alternative_groups : list of list of str, optional
        Groups of filenames that are alternatives to each other (only one
        active at runtime). Duplicate ids between files in the same group
        are suppressed.
    xios_version : str, optional
        XIOS version to validate against (e.g. ``"2"`` or ``"3"``).
        Defaults to ``"2"``.
    jinja_vars : dict, optional
        Variables passed to the Jinja2 renderer when linting ``.xml.j2``
        files. When provided, conditional blocks collapse to the matching
        branch instead of preserving both, which is what lets a unified
        multi-version template lint cleanly under a specific XIOS
        version. When omitted, the legacy regex-based stripping is used.
    """

    def __init__(self, alternative_groups=None, xios_version=None,
                 jinja_vars=None):
        self.schema = get_schema(xios_version or DEFAULT_VERSION)
        self.jinja_vars = jinja_vars or None
        self.errors = []
        self.warnings = []
        self.ids = {}  # id -> (file, element_tag, line)
        self.refs = []  # (ref_attr, ref_value, file, line, element_tag)
        self.src_ids = set()  # ids from elements with src= (inclusion pointers)
        self.alt_groups = {}  # filename pattern -> group_index
        if alternative_groups:
            for group_idx, group in enumerate(alternative_groups):
                for pattern in group:
                    self.alt_groups[pattern.strip()] = group_idx

    def _get_alt_group(self, filepath):
        """Return the alternative group index for a file, or None."""
        name = Path(filepath).name
        for pattern, group_idx in self.alt_groups.items():
            if fnmatch.fnmatch(name, pattern) or name == pattern:
                return group_idx
        return None

    def _same_alt_group(self, file_a, file_b):
        """True if both files belong to the same alternative group."""
        ga = self._get_alt_group(file_a)
        gb = self._get_alt_group(file_b)
        return ga is not None and ga == gb

    def error(self, filepath, line, msg):
        self.errors.append(f"{filepath}:{line}: ERROR: {msg}")

    def warn(self, filepath, line, msg):
        self.warnings.append(f"{filepath}:{line}: WARNING: {msg}")

    def lint_file(self, filepath):
        """Lint a single XIOS XML or XML.j2 file."""
        path = Path(filepath)
        is_jinja = path.suffix == ".j2" or ".j2" in path.suffixes

        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            self.error(filepath, 0, f"Cannot read file: {e}")
            return

        if is_jinja:
            text = preprocess_jinja(text, variables=self.jinja_vars)

        try:
            tree = etree.fromstring(text.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            self.error(filepath, e.lineno or 0, f"XML syntax error: {e}")
            return

        self._walk(tree, filepath)

    def _walk(self, element, filepath):
        """Recursively validate an element and its children."""
        tag = element.tag
        line = element.sourceline or 0
        schema = self.schema

        # Check element name
        if tag not in schema.valid_elements:
            self.warn(filepath, line, f"Unknown element <{tag}>")

        # Check attributes
        known_attrs = schema.element_attrs.get(tag, schema.common_attrs)
        for attr in element.attrib:
            if attr not in known_attrs:
                self.warn(filepath, line, f"Unknown attribute '{attr}' on <{tag}>")

        # Track elements with src= (inclusion pointers)
        has_src = "src" in element.attrib

        # Collect ids
        elem_id = element.get("id")
        if elem_id:
            if has_src:
                self.src_ids.add(elem_id)
            elif elem_id in self.ids:
                prev_file, prev_tag, prev_line = self.ids[elem_id]
                if self._same_alt_group(filepath, prev_file):
                    pass  # expected duplicate between alternatives
                elif elem_id in self.src_ids:
                    pass  # previous was a src= inclusion pointer
                else:
                    self.error(
                        filepath, line,
                        f"Duplicate id='{elem_id}' "
                        f"(first defined in {prev_file}:{prev_line} on <{prev_tag}>)"
                    )
            else:
                self.ids[elem_id] = (filepath, tag, line)

        # Collect refs for later resolution
        for attr in element.attrib:
            if attr.endswith("_ref"):
                ref_val = element.get(attr)
                if ref_val and not ref_val.startswith("JINJA_PLACEHOLDER"):
                    self.refs.append((attr, ref_val, filepath, line, tag))

        # Validate enum attributes
        self._check_enum(element, "operation", schema.valid_operations, filepath, line, tag)
        if tag in ("file", "file_group"):
            self._check_enum(element, "type", schema.valid_file_types, filepath, line, tag)
            self._check_enum(element, "format", schema.valid_file_formats, filepath, line, tag)
            self._check_enum(element, "mode", schema.valid_file_modes, filepath, line, tag)
            self._check_enum(element, "par_access", schema.valid_par_access, filepath, line, tag)
            self._check_enum(element, "timeseries", schema.valid_timeseries, filepath, line, tag)
            self._check_enum(element, "convention", schema.valid_conventions, filepath, line, tag)
        if tag == "calendar":
            self._check_enum(element, "type", schema.valid_calendar_types, filepath, line, tag)
        if tag in ("domain", "domain_group"):
            self._check_enum(element, "type", schema.valid_domain_types, filepath, line, tag)
        if tag in ("axis", "axis_group"):
            self._check_enum(element, "positive", schema.valid_positive, filepath, line, tag)

        # Check fields in field_definition have an id
        if tag == "field":
            has_field_ref = "field_ref" in element.attrib
            has_id = "id" in element.attrib

            in_field_def = False
            parent = element.getparent()
            while parent is not None:
                if parent.tag == "field_definition":
                    in_field_def = True
                    break
                parent = parent.getparent()

            if in_field_def and not has_field_ref and not has_id:
                self.warn(filepath, line, "<field> in field_definition should have 'id'")

        # Check file has output_freq
        if tag == "file":
            if "output_freq" not in element.attrib:
                parent = element.getparent()
                parent_has_freq = False
                while parent is not None:
                    if parent.tag == "file_group" and "output_freq" in parent.attrib:
                        parent_has_freq = True
                        break
                    parent = parent.getparent()
                if not parent_has_freq:
                    self.warn(filepath, line, "<file> missing 'output_freq' (not inherited from parent)")

        # Recurse
        for child in element:
            if isinstance(child.tag, str):
                self._walk(child, filepath)

    def _check_enum(self, element, attr, valid_values, filepath, line, tag):
        """Check if an attribute value is in the allowed set."""
        val = element.get(attr)
        if val and not val.startswith("JINJA_PLACEHOLDER"):
            val_clean = val.strip().strip("'\"")
            if val_clean not in valid_values:
                self.error(
                    filepath, line,
                    f"Invalid {attr}='{val_clean}' on <{tag}> "
                    f"(expected one of: {', '.join(sorted(valid_values))})"
                )

    def check_refs(self):
        """After all files are parsed, check that all references resolve."""
        for attr, ref_val, filepath, line, tag in self.refs:
            if ref_val not in self.ids:
                if attr == "src":
                    continue
                self.warn(
                    filepath, line,
                    f"Unresolved {attr}='{ref_val}' on <{tag}> "
                    f"(no element with id='{ref_val}' found)"
                )

    def report(self):
        """Print results and return exit code."""
        for w in sorted(self.warnings):
            print(f"  {w}")
        for e in sorted(self.errors):
            print(f"  {e}")

        n_err = len(self.errors)
        n_warn = len(self.warnings)
        n_ids = len(self.ids)

        print(f"\n  {n_ids} ids collected, {len(self.refs)} references checked")
        if n_err == 0 and n_warn == 0:
            print("  All checks passed.")
        else:
            if n_warn:
                print(f"  {n_warn} warning(s)")
            if n_err:
                print(f"  {n_err} error(s)")

        return 1 if n_err > 0 else 0
