"""Tests for the XIOS XML linter."""

import textwrap
from pathlib import Path

import pytest

from lint_xios_xml.linter import XiosLinter, preprocess_jinja
from lint_xios_xml.schemas import get_schema, list_versions


@pytest.fixture
def tmp_xml(tmp_path):
    """Helper to write XML content to a temporary file and return its path."""
    def _write(content, name="test.xml"):
        p = tmp_path / name
        p.write_text(textwrap.dedent(content))
        return str(p)
    return _write


class TestPreprocessJinja:
    def test_expression_replaced(self):
        assert "JINJA_PLACEHOLDER" in preprocess_jinja("val={{foo}}")

    def test_block_stripped(self):
        assert "{% if" not in preprocess_jinja("{% if x %}hello{% endif %}")

    def test_comment_stripped(self):
        assert "{#" not in preprocess_jinja("{# a comment #}")

    def test_no_vars_preserves_both_if_branches(self):
        """Backward-compat: without vars, regex strips {% %} and both
        branches remain."""
        out = preprocess_jinja(
            "{% if x %}A{% else %}B{% endif %}"
        )
        assert "A" in out and "B" in out


class TestJinja2Rendering:
    """Full Jinja2 rendering is activated when ``variables`` is provided."""

    def test_if_branch_selected_xios3(self):
        out = preprocess_jinja(
            "{% if xios.version.startswith('3') %}X3{% else %}X2{% endif %}",
            variables={"xios": {"version": "3.0"}},
        )
        assert "X3" in out and "X2" not in out

    def test_if_branch_selected_xios2(self):
        out = preprocess_jinja(
            "{% if xios.version.startswith('3') %}X3{% else %}X2{% endif %}",
            variables={"xios": {"version": "2.5"}},
        )
        assert "X2" in out and "X3" not in out

    def test_undefined_variable_becomes_placeholder(self):
        """Undefined names must not crash — they resolve to JINJA_PLACEHOLDER."""
        out = preprocess_jinja(
            "value={{ undefined_var }}",
            variables={"xios": {"version": "3.0"}},
        )
        assert "JINJA_PLACEHOLDER" in out

    def test_undefined_nested_access_ok(self):
        out = preprocess_jinja(
            "value={{ a.b.c.d }}",
            variables={"xios": {"version": "3.0"}},
        )
        assert "JINJA_PLACEHOLDER" in out

    def test_undefined_in_if_is_falsy(self):
        """{% if undefined %} takes the else branch, not a crash."""
        out = preprocess_jinja(
            "{% if missing_thing %}A{% else %}B{% endif %}",
            variables={"xios": {"version": "3.0"}},
        )
        assert "B" in out and "A" not in out

    def test_linter_with_jinja_vars_picks_xios3_branch(self, tmp_xml):
        """End-to-end: linter with jinja_vars sees only the chosen branch,
        so a unified iodef template lints cleanly under the right version."""
        content = (
            '<simulation><context id="xios"><variable_definition>'
            '<variable_group id="parameters">'
            '{% if xios.version.startswith("3") %}'
            '<variable id="clients_code_id" type="string">OpenIFS</variable>'
            '{% else %}'
            '<variable id="oasis_codes_id" type="string">OpenIFS</variable>'
            '{% endif %}'
            '</variable_group>'
            '</variable_definition></context></simulation>'
        )
        linter = XiosLinter(
            xios_version="3",
            jinja_vars={"xios": {"version": "3.0"}},
        )
        linter.lint_file(tmp_xml(content, name="iodef.xml.j2"))
        assert not any("oasis_codes_id" in w for w in linter.warnings)
        assert not any("clients_code_id" in w for w in linter.warnings)

    def test_linter_without_jinja_vars_preserves_both_branches(self, tmp_xml):
        """Backward-compat: no jinja_vars → both branches survive in the parse tree."""
        content = (
            '<simulation><context id="xios"><variable_definition>'
            '{% if xios.version.startswith("3") %}'
            '<variable_group id="grp_3"></variable_group>'
            '{% else %}'
            '<variable_group id="grp_2"></variable_group>'
            '{% endif %}'
            '</variable_definition></context></simulation>'
        )
        linter = XiosLinter()
        linter.lint_file(tmp_xml(content, name="iodef.xml.j2"))
        # Both ids present → ``{% %}`` strip left both branches intact.
        assert "grp_3" in linter.ids and "grp_2" in linter.ids


class TestCliDefine:
    """CLI ``--define`` flag builds nested dicts for Jinja2 rendering."""

    def test_parse_defines_nested(self):
        from lint_xios_xml.cli import _parse_defines
        out = _parse_defines(["xios.version=3.0", "oifs.resolution=TCO95"])
        assert out == {"xios": {"version": "3.0"},
                       "oifs": {"resolution": "TCO95"}}

    def test_parse_defines_requires_equals(self):
        from lint_xios_xml.cli import _parse_defines
        with pytest.raises(SystemExit):
            _parse_defines(["no_equals_here"])

    def test_cli_define_selects_branch(self, tmp_path):
        """Full CLI path: --define xios.version=3.0 picks the XIOS 3 branch."""
        import sys

        f = tmp_path / "iodef.xml.j2"
        f.write_text(
            '<simulation><context id="xios"><variable_definition>'
            '<variable_group id="p">'
            '{% if xios.version.startswith("3") %}'
            '<variable id="clients_code_id" type="string">x</variable>'
            '{% else %}'
            '<variable id="oasis_codes_id" type="string">x</variable>'
            '{% endif %}'
            '</variable_group>'
            '</variable_definition></context></simulation>'
        )

        from lint_xios_xml import cli as cli_mod
        import io
        import contextlib

        buf = io.StringIO()
        old_argv = sys.argv
        try:
            sys.argv = [
                "lint-xios-xml", "--xios-version", "3",
                "--define", "xios.version=3.0",
                str(f),
            ]
            with contextlib.redirect_stdout(buf):
                code = cli_mod.main()
        finally:
            sys.argv = old_argv

        out = buf.getvalue()
        # Should not flag either variable as cross-version — only the
        # XIOS 3 branch survives the render.
        assert "oasis_codes_id" not in out
        assert "clients_code_id" not in out
        # A clean XIOS 3 template of this shape should lint cleanly.
        assert code == 0


class TestWellFormedXML:
    def test_valid_xml(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml('<field_definition><field id="t" /></field_definition>'))
        assert len(linter.errors) == 0

    def test_broken_xml(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml("<field><unclosed>"))
        assert any("XML syntax error" in e for e in linter.errors)

    def test_jinja_template(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<file_group compression_level="{{xios.level}}"><file output_freq="1mo" /></file_group>',
            name="test.xml.j2",
        ))
        assert len(linter.errors) == 0


class TestElementValidation:
    def test_unknown_element(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml("<simulation><bogus_element /></simulation>"))
        assert any("Unknown element <bogus_element>" in w for w in linter.warnings)

    def test_known_elements(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<field_definition><field id="x" operation="average" /></field_definition>'
        ))
        assert len(linter.warnings) == 0


class TestAttributeValidation:
    def test_unknown_attribute(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml('<field_definition><field id="x" bogus="y" /></field_definition>'))
        assert any("Unknown attribute 'bogus'" in w for w in linter.warnings)

    def test_valid_attributes(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<field_definition><field id="x" long_name="Temperature" unit="K" /></field_definition>'
        ))
        assert len(linter.warnings) == 0


class TestEnumValidation:
    def test_invalid_operation(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<field_definition><field id="x" operation="bogus" /></field_definition>'
        ))
        assert any("Invalid operation='bogus'" in e for e in linter.errors)

    def test_valid_operation(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<field_definition><field id="x" operation="average" /></field_definition>'
        ))
        assert len(linter.errors) == 0

    def test_invalid_file_type(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<file_definition><file type="wrong" output_freq="1mo" /></file_definition>'
        ))
        assert any("Invalid type='wrong'" in e for e in linter.errors)

    def test_invalid_domain_type(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<domain_definition><domain id="d" type="spherical" /></domain_definition>'
        ))
        assert any("Invalid type='spherical'" in e for e in linter.errors)

    def test_gaussian_domain_type(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<domain_definition><domain id="d" type="gaussian" /></domain_definition>'
        ))
        assert len(linter.errors) == 0


class TestDuplicateIds:
    def test_duplicate_in_same_file(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<field_definition><field id="dup" /><field id="dup" /></field_definition>'
        ))
        assert any("Duplicate id='dup'" in e for e in linter.errors)

    def test_duplicate_across_files(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml('<field_definition><field id="x" /></field_definition>', name="a.xml"))
        linter.lint_file(tmp_xml('<field_definition><field id="x" /></field_definition>', name="b.xml"))
        assert any("Duplicate id='x'" in e for e in linter.errors)

    def test_alternatives_suppress_duplicates(self, tmp_xml):
        linter = XiosLinter(alternative_groups=[["a.xml", "b.xml"]])
        linter.lint_file(tmp_xml('<field_definition><field id="x" /></field_definition>', name="a.xml"))
        linter.lint_file(tmp_xml('<field_definition><field id="x" /></field_definition>', name="b.xml"))
        assert len(linter.errors) == 0

    def test_src_inclusion_not_duplicate(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml('<simulation><context id="ctx" src="./other.xml" /></simulation>', name="io.xml"))
        linter.lint_file(tmp_xml('<context id="ctx"><field_definition /></context>', name="other.xml"))
        assert len(linter.errors) == 0


class TestReferenceChecking:
    def test_resolved_ref(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<field_definition>'
            '  <field id="temp" />'
            '  <field field_ref="temp" />'
            '</field_definition>'
        ))
        linter.check_refs()
        assert len(linter.warnings) == 0

    def test_unresolved_ref(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<field_definition><field field_ref="nonexistent" /></field_definition>'
        ))
        linter.check_refs()
        assert any("Unresolved field_ref='nonexistent'" in w for w in linter.warnings)

    def test_cross_file_ref(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<field_definition><field id="sst" /></field_definition>', name="fields.xml"
        ))
        linter.lint_file(tmp_xml(
            '<file_definition><file output_freq="1mo"><field field_ref="sst" /></file></file_definition>',
            name="files.xml",
        ))
        linter.check_refs()
        assert len(linter.warnings) == 0


class TestFileChecks:
    def test_missing_output_freq(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<file_definition><file enabled="true" /></file_definition>'
        ))
        assert any("missing 'output_freq'" in w for w in linter.warnings)

    def test_output_freq_inherited(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<file_definition><file_group output_freq="1mo"><file enabled="true" /></file_group></file_definition>'
        ))
        assert not any("missing 'output_freq'" in w for w in linter.warnings)


class TestFieldChecks:
    def test_field_in_def_needs_id(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<field_definition><field long_name="oops" /></field_definition>'
        ))
        assert any("should have 'id'" in w for w in linter.warnings)


# -------------------------------------------------------------------
# Version-aware tests
# -------------------------------------------------------------------

class TestVersionRegistry:
    def test_list_versions(self):
        versions = list_versions()
        assert "2" in versions
        assert "3" in versions

    def test_get_schema_valid(self):
        schema = get_schema("2")
        assert schema.version == "2"
        assert "field" in schema.valid_elements

    def test_get_schema_invalid(self):
        with pytest.raises(ValueError, match="Unknown XIOS version"):
            get_schema("999")

    def test_default_version_is_xios2(self, tmp_xml):
        linter = XiosLinter()
        assert linter.schema.version == "2"


class TestXios2Schema:
    def test_xios2_rejects_xios3_element(self, tmp_xml):
        """Elements added in XIOS 3 should warn under XIOS 2."""
        linter = XiosLinter(xios_version="2")
        linter.lint_file(tmp_xml("<simulation><pool /></simulation>"))
        assert any("Unknown element <pool>" in w for w in linter.warnings)

    def test_xios2_knows_zoom_domain(self, tmp_xml):
        linter = XiosLinter(xios_version="2")
        linter.lint_file(tmp_xml(
            '<grid_definition><grid id="g"><zoom_domain /></grid></grid_definition>'
        ))
        assert not any("Unknown element <zoom_domain>" in w for w in linter.warnings)


class TestXios3Schema:
    def test_xios3_accepts_pool(self, tmp_xml):
        """<pool> is valid in XIOS 3."""
        linter = XiosLinter(xios_version="3")
        linter.lint_file(tmp_xml("<simulation><pool /></simulation>"))
        assert not any("Unknown element <pool>" in w for w in linter.warnings)

    def test_xios3_accepts_service(self, tmp_xml):
        """<service> and <services> are valid in XIOS 3."""
        linter = XiosLinter(xios_version="3")
        linter.lint_file(tmp_xml(
            "<simulation><services><service /></services></simulation>"
        ))
        assert not any("Unknown element" in w for w in linter.warnings)

    def test_xios3_still_validates_xios2_elements(self, tmp_xml):
        """XIOS 3 should still validate all XIOS 2 elements correctly."""
        linter = XiosLinter(xios_version="3")
        linter.lint_file(tmp_xml(
            '<field_definition><field id="x" operation="average" /></field_definition>'
        ))
        assert len(linter.errors) == 0
        assert len(linter.warnings) == 0

    def test_xios3_context_attached_mode(self, tmp_xml):
        """context should accept attached_mode in XIOS 3."""
        linter = XiosLinter(xios_version="3")
        linter.lint_file(tmp_xml('<context id="c" attached_mode="true" />'))
        assert not any("Unknown attribute 'attached_mode'" in w for w in linter.warnings)

    def test_xios2_rejects_attached_mode(self, tmp_xml):
        """context should NOT accept attached_mode in XIOS 2."""
        linter = XiosLinter(xios_version="2")
        linter.lint_file(tmp_xml('<context id="c" attached_mode="true" />'))
        assert any("Unknown attribute 'attached_mode'" in w for w in linter.warnings)


class TestExplicitVersion:
    def test_explicit_version_parameter(self, tmp_xml):
        """XiosLinter should use the specified version."""
        linter = XiosLinter(xios_version="3")
        assert linter.schema.version == "3"


class TestVariableVersionGate:
    """Well-known ``<variable id="...">`` tokens get per-version warnings."""

    def _iodef(self, var_id):
        return (
            "<simulation><context id=\"xios\"><variable_definition>"
            f"<variable id=\"{var_id}\" type=\"string\">v</variable>"
            "</variable_definition></context></simulation>"
        )

    def test_oasis_codes_id_warns_on_xios3(self, tmp_xml):
        linter = XiosLinter(xios_version="3")
        linter.lint_file(tmp_xml(self._iodef("oasis_codes_id")))
        assert any(
            "oasis_codes_id" in w
            and "clients_code_id" in w
            and "XIOS 3" in w
            for w in linter.warnings
        )

    def test_oasis_codes_id_ok_on_xios2(self, tmp_xml):
        linter = XiosLinter(xios_version="2")
        linter.lint_file(tmp_xml(self._iodef("oasis_codes_id")))
        assert not any("oasis_codes_id" in w for w in linter.warnings)

    def test_clients_code_id_warns_on_xios2(self, tmp_xml):
        linter = XiosLinter(xios_version="2")
        linter.lint_file(tmp_xml(self._iodef("clients_code_id")))
        assert any(
            "clients_code_id" in w
            and "oasis_codes_id" in w
            for w in linter.warnings
        )

    def test_clients_code_id_ok_on_xios3(self, tmp_xml):
        linter = XiosLinter(xios_version="3")
        linter.lint_file(tmp_xml(self._iodef("clients_code_id")))
        assert not any("clients_code_id" in w for w in linter.warnings)

    def test_call_oasis_enddef_only_xios3(self, tmp_xml):
        linter2 = XiosLinter(xios_version="2")
        linter2.lint_file(tmp_xml(self._iodef("call_oasis_enddef")))
        assert any("call_oasis_enddef" in w for w in linter2.warnings)

        linter3 = XiosLinter(xios_version="3")
        linter3.lint_file(tmp_xml(self._iodef("call_oasis_enddef")))
        assert not any("call_oasis_enddef" in w for w in linter3.warnings)

    def test_unknown_variable_id_ignored(self, tmp_xml):
        """Ids not in the registry are not flagged."""
        linter = XiosLinter(xios_version="2")
        linter.lint_file(tmp_xml(self._iodef("using_server")))
        assert not any("using_server" in w for w in linter.warnings)


class TestSchemaFills:
    """New attributes/elements accepted after schema backfill."""

    def test_axis_group_axis_type(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<axis_definition><axis_group axis_type="Z"><axis id="a" /></axis_group></axis_definition>'
        ))
        assert not any("axis_type" in w for w in linter.warnings)

    def test_domain_dim_i_name(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<domain_definition><domain id="d" dim_i_name="nod2" /></domain_definition>'
        ))
        assert not any("dim_i_name" in w for w in linter.warnings)

    def test_file_definition_inherits_file_attrs(self, tmp_xml):
        linter = XiosLinter()
        linter.lint_file(tmp_xml(
            '<file_definition type="one_file" format="netcdf4" par_access="collective"'
            ' compression_level="1" time_counter="exclusive" time_counter_name="time">'
            '<file output_freq="1mo" /></file_definition>'
        ))
        assert not any(
            any(a in w for a in ("type", "format", "par_access",
                                 "compression_level", "time_counter"))
            for w in linter.warnings
        )

    def test_xios3_extract_axis(self, tmp_xml):
        linter = XiosLinter(xios_version="3")
        linter.lint_file(tmp_xml(
            '<axis_definition><axis id="a">'
            '<extract_axis index="(0,1)[0 2]" />'
            '</axis></axis_definition>'
        ))
        assert not any("extract_axis" in w for w in linter.warnings)

    def test_xios3_file_service_routing_attrs(self, tmp_xml):
        linter = XiosLinter(xios_version="3")
        linter.lint_file(tmp_xml(
            '<file_definition><file output_freq="1h" writer="srv_w"'
            ' gatherer="srv_g" using_server2="true" /></file_definition>'
        ))
        assert not any(
            any(a in w for a in ("writer", "gatherer", "using_server2"))
            for w in linter.warnings
        )
