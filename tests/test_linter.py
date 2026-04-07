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
