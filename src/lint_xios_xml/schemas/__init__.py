"""Version-aware XIOS schema definitions.

Each supported XIOS version is defined in its own module (e.g. xios2, xios3).
Use ``get_schema(version)`` to obtain the schema for a specific version.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Set


@dataclass
class XiosSchema:
    """Complete schema definition for one XIOS version."""

    version: str

    # Valid element names
    valid_elements: Set[str] = field(default_factory=set)

    # Attributes common to most elements
    common_attrs: Set[str] = field(default_factory=set)

    # Per-element attribute sets (tag -> set of allowed attribute names)
    element_attrs: Dict[str, Set[str]] = field(default_factory=dict)

    # Enum constraints
    valid_operations: Set[str] = field(default_factory=set)
    valid_file_types: Set[str] = field(default_factory=set)
    valid_file_formats: Set[str] = field(default_factory=set)
    valid_file_modes: Set[str] = field(default_factory=set)
    valid_par_access: Set[str] = field(default_factory=set)
    valid_calendar_types: Set[str] = field(default_factory=set)
    valid_timeseries: Set[str] = field(default_factory=set)
    valid_conventions: Set[str] = field(default_factory=set)
    valid_domain_types: Set[str] = field(default_factory=set)
    valid_positive: Set[str] = field(default_factory=set)

    # Known XIOS <variable id="..."> tokens inside <variable_definition>,
    # keyed by id. Each entry may have:
    #   ``valid_versions``: set of XIOS versions in which the id is valid
    #   ``renamed_to``:     id name in a later version (shown in warnings)
    #   ``renamed_from``:   id name in an earlier version
    #
    # The linter warns when a file lints under a version whose id is
    # present in this registry but absent from ``valid_versions``.
    known_variable_ids: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shared registry of version-gated <variable id="..."> tokens
# ---------------------------------------------------------------------------

# Populated into every schema's ``known_variable_ids`` below. Each value may
# carry ``valid_versions``, ``renamed_to``, ``renamed_from``.
KNOWN_VARIABLE_IDS: Dict[str, Dict[str, Any]] = {
    # --- XIOS 2 / XIOS 3 OASIS identifier rename ---
    "oasis_codes_id": {
        "valid_versions": {"2"},
        "renamed_to": "clients_code_id",
    },
    "clients_code_id": {
        "valid_versions": {"3"},
        "renamed_from": "oasis_codes_id",
    },
    # --- XIOS 3-only additions ---
    "call_oasis_enddef": {
        "valid_versions": {"3"},
    },
}


# ---------------------------------------------------------------------------
# Version registry
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, XiosSchema] = {}

DEFAULT_VERSION = "2"


def register(schema: XiosSchema) -> None:
    """Register a schema under its version string."""
    _REGISTRY[schema.version] = schema


def get_schema(version: str) -> XiosSchema:
    """Return the schema for the given XIOS version.

    Raises ``ValueError`` if the version is unknown.
    """
    if version not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown XIOS version '{version}'. Available versions: {available}"
        )
    return _REGISTRY[version]


def list_versions():
    """Return sorted list of registered version strings."""
    return sorted(_REGISTRY)


# Import version modules so they self-register on first import.
from lint_xios_xml.schemas import xios2 as _xios2  # noqa: E402, F401
from lint_xios_xml.schemas import xios3 as _xios3  # noqa: E402, F401
