"""Version-aware XIOS schema definitions.

Each supported XIOS version is defined in its own module (e.g. xios2, xios3).
Use ``get_schema(version)`` to obtain the schema for a specific version.
"""

from dataclasses import dataclass, field
from typing import Dict, Set


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
