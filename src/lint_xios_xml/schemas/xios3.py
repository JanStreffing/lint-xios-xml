"""XIOS 3.x schema definitions.

Built on top of the XIOS 2 schema, with additions and modifications for the
XIOS 3 architecture (redesigned client/server, new workflow elements, etc.).

To customize: edit the sets below.  Adding an element or attribute is as
simple as adding a string to the relevant set.
"""

import copy

from lint_xios_xml.schemas import KNOWN_VARIABLE_IDS, XiosSchema, register
from lint_xios_xml.schemas.xios2 import SCHEMA as XIOS2_SCHEMA

# Start from a deep copy of XIOS 2
SCHEMA = copy.deepcopy(XIOS2_SCHEMA)
SCHEMA.version = "3"
SCHEMA.known_variable_ids = KNOWN_VARIABLE_IDS

# -------------------------------------------------------------------
# New elements in XIOS 3
# -------------------------------------------------------------------
SCHEMA.valid_elements |= {
    # Server architecture
    "pool",
    "service",
    "services",
    # Coupling
    "coupling_input",
    "coupling_output",
    # Transformations added in XIOS 3
    "compute_connectivity_domain",
    "expand_domain",
    "extract_domain",
    "extract_axis",
    "redistribute",
}

# -------------------------------------------------------------------
# New / modified attributes in XIOS 3
# -------------------------------------------------------------------

# context gained attributes for the new server architecture
SCHEMA.element_attrs["context"] |= {
    "attached_mode",
}

# New elements need attribute definitions
SCHEMA.element_attrs["pool"] = SCHEMA.common_attrs | {
    "buffer_size", "buffer_server_factor_size",
    "min_buffer_size", "max_buffer_size",
    "n_server", "n_server2",
}
SCHEMA.element_attrs["services"] = SCHEMA.common_attrs
SCHEMA.element_attrs["service"] = SCHEMA.common_attrs | {
    "type", "n_server",
}
SCHEMA.element_attrs["coupling_input"] = SCHEMA.common_attrs | {
    "field_ref", "grid_ref", "freq_op", "operation",
}
SCHEMA.element_attrs["coupling_output"] = SCHEMA.common_attrs | {
    "field_ref", "grid_ref", "freq_op", "operation",
}
SCHEMA.element_attrs["compute_connectivity_domain"] = SCHEMA.common_attrs | {
    "type",
}
SCHEMA.element_attrs["expand_domain"] = SCHEMA.common_attrs | {
    "type", "i_periodic", "j_periodic",
}
SCHEMA.element_attrs["extract_domain"] = SCHEMA.common_attrs | {
    "ibegin", "ni", "jbegin", "nj",
}
SCHEMA.element_attrs["extract_axis"] = SCHEMA.common_attrs | {
    "begin", "n", "index",
}
SCHEMA.element_attrs["redistribute"] = SCHEMA.common_attrs

# file element gained new attributes in XIOS 3
SCHEMA.element_attrs["file"] |= {
    "time_stamp_name", "time_stamp_format",
    "uuid_name", "uuid_format",
    # Service/pool routing for the redesigned XIOS 3 server
    "reader", "writer", "gatherer", "using_server2",
}
SCHEMA.element_attrs["file_group"] |= {
    "time_stamp_name", "time_stamp_format",
    "uuid_name", "uuid_format",
    "reader", "writer", "gatherer", "using_server2",
}

register(SCHEMA)
