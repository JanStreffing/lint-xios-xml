"""XIOS element/attribute schema definitions (from XIOS User Guide + Reference)."""

VALID_ELEMENTS = {
    # Top-level
    "simulation",
    "context",
    # Definitions
    "field_definition",
    "file_definition",
    "grid_definition",
    "domain_definition",
    "axis_definition",
    "variable_definition",
    # Groups
    "field_group",
    "file_group",
    "grid_group",
    "domain_group",
    "axis_group",
    "variable_group",
    # Core elements
    "field",
    "file",
    "grid",
    "domain",
    "axis",
    "variable",
    "calendar",
    # Grid sub-elements
    "scalar",
    # Transformations
    "zoom_domain",
    "zoom_axis",
    "interpolate_domain",
    "interpolate_axis",
    "generate_rectilinear_domain",
    "inverse_axis",
    "reduce_domain_to_axis",
    "extract_domain_to_axis",
    "reduce_axis_to_scalar",
    "reduce_axis_to_axis",
    "temporal_splitting",
    "duplicate_scalar_to_axis",
    "extract_axis_to_scalar",
    "redistribute_domain",
    "redistribute_axis",
    "reorder_domain",
}

# Common attributes that can appear on most elements
COMMON_ATTRS = {"id", "name", "enabled", "src", "description", "comment"}

# Attributes valid per element type
ELEMENT_ATTRS = {
    "simulation": COMMON_ATTRS,
    "context": COMMON_ATTRS | {"type", "calendar_type"},
    "calendar": COMMON_ATTRS | {
        "type", "timestep", "start_date", "time_origin",
        "day_length", "month_lengths", "year_length",
        "leap_year_drift", "leap_year_month", "leap_year_drift_offset",
    },
    "field": COMMON_ATTRS | {
        "field_ref", "grid_ref", "domain_ref", "axis_ref", "scalar_ref",
        "operation", "freq_op", "freq_offset",
        "long_name", "standard_name", "unit",
        "prec", "level", "default_value",
        "compression_level", "indexed_output",
        "detect_missing_value", "read_access",
        "cell_methods", "cell_methods_mode",
        "ts_enabled", "ts_split_freq",
        "expr", "field_id",
        "check_if_active",
    },
    "field_definition": COMMON_ATTRS | {
        "level", "prec", "enabled", "operation", "freq_op",
        "ts_enabled", "default_value",
    },
    "field_group": COMMON_ATTRS | {
        "field_ref", "grid_ref", "domain_ref", "axis_ref", "scalar_ref",
        "operation", "freq_op", "freq_offset",
        "long_name", "standard_name", "unit",
        "prec", "level", "default_value",
        "compression_level", "detect_missing_value",
        "ts_enabled", "ts_split_freq",
        "cell_methods", "cell_methods_mode",
    },
    "file": COMMON_ATTRS | {
        "output_freq", "output_level", "split_freq", "split_freq_format",
        "sync_freq", "type", "format", "par_access",
        "mode", "append", "convention",
        "timeseries", "ts_prefix",
        "compression_level", "name_suffix",
        "min_digits", "record_offset",
        "cyclic",
    },
    "file_definition": COMMON_ATTRS,
    "file_group": COMMON_ATTRS | {
        "output_freq", "output_level", "split_freq", "split_freq_format",
        "sync_freq", "type", "format", "par_access",
        "mode", "append", "convention",
        "timeseries", "ts_prefix",
        "compression_level", "name_suffix",
        "min_digits",
    },
    "grid": COMMON_ATTRS | {"grid_ref"},
    "grid_definition": COMMON_ATTRS,
    "grid_group": COMMON_ATTRS,
    "domain": COMMON_ATTRS | {
        "domain_ref", "type", "long_name",
        "ni_glo", "nj_glo", "ibegin", "jbegin", "ni", "nj",
        "data_dim", "data_ni", "data_nj", "data_ibegin", "data_jbegin",
        "lonvalue_1d", "latvalue_1d", "lonvalue_2d", "latvalue_2d",
        "bounds_lon_1d", "bounds_lat_1d", "bounds_lon_2d", "bounds_lat_2d",
        "i_index", "j_index", "data_i_index", "data_j_index",
        "nvertex", "area",
    },
    "domain_definition": COMMON_ATTRS,
    "domain_group": COMMON_ATTRS | {"type", "long_name"},
    "axis": COMMON_ATTRS | {
        "axis_ref", "long_name", "standard_name", "unit",
        "positive", "n_glo", "value", "bounds", "label",
        "index", "begin", "n", "data_begin", "data_n", "data_index",
        "prec",
    },
    "axis_definition": COMMON_ATTRS,
    "axis_group": COMMON_ATTRS | {"unit", "positive", "long_name", "standard_name"},
    "variable": COMMON_ATTRS | {"type"},
    "variable_definition": COMMON_ATTRS,
    "variable_group": COMMON_ATTRS,
    "scalar": COMMON_ATTRS | {
        "scalar_ref", "long_name", "standard_name", "unit", "value", "prec",
    },
    # Transformations
    "zoom_domain": COMMON_ATTRS | {"zoom_ibegin", "zoom_ni", "zoom_jbegin", "zoom_nj"},
    "zoom_axis": COMMON_ATTRS | {"begin", "n", "index"},
    "interpolate_domain": COMMON_ATTRS | {
        "order", "type", "weight_filename", "write_weight",
        "renormalize", "quantity", "mode",
        "detect_missing_value",
    },
    "interpolate_axis": COMMON_ATTRS | {"order", "type"},
    "generate_rectilinear_domain": COMMON_ATTRS | {
        "lat_start", "lat_end", "lon_start", "lon_end",
        "bounds_lat_start", "bounds_lat_end",
        "bounds_lon_start", "bounds_lon_end",
    },
    "inverse_axis": COMMON_ATTRS,
    "reduce_domain_to_axis": COMMON_ATTRS | {"direction", "operation"},
    "extract_domain_to_axis": COMMON_ATTRS | {"position"},
    "reduce_axis_to_scalar": COMMON_ATTRS | {"operation"},
    "reduce_axis_to_axis": COMMON_ATTRS | {"operation"},
    "temporal_splitting": COMMON_ATTRS,
    "duplicate_scalar_to_axis": COMMON_ATTRS,
    "extract_axis_to_scalar": COMMON_ATTRS | {"position"},
    "redistribute_domain": COMMON_ATTRS,
    "redistribute_axis": COMMON_ATTRS,
    "reorder_domain": COMMON_ATTRS | {"invert_lat"},
}

# Enum constraints
VALID_OPERATIONS = {"instant", "average", "accumulate", "minimum", "maximum", "once"}
VALID_FILE_TYPES = {"one_file", "multiple_file"}
VALID_FILE_FORMATS = {"netcdf4", "netcdf4_classic"}
VALID_FILE_MODES = {"write", "read"}
VALID_PAR_ACCESS = {"collective", "independent"}
VALID_CALENDAR_TYPES = {
    "Gregorian", "Julian", "NoLeap", "AllLeap", "D360",
    "user_defined",
    # case-insensitive aliases
    "gregorian", "julian", "noleap", "allleap", "d360",
}
VALID_TIMESERIES = {"none", "only", "both", "exclusive"}
VALID_CONVENTIONS = {"CF", "UGRID"}
VALID_DOMAIN_TYPES = {
    "rectilinear", "curvilinear", "unstructured",
    "gaussian", "gaussian_reduced",
}
VALID_POSITIVE = {"up", "down"}
