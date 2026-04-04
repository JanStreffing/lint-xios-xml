"""Tests for the XIOS XML linter."""

import textwrap
from pathlib import Path

import pytest

from lint_xios_xml.linter import XiosLinter, preprocess_jinja


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
