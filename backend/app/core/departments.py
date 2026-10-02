"""
Single source of truth for the Department / Sub-department list and the 6
data-type categories.

To rename or add departments: edit DEPARTMENTS below.  No other file needs
to change — the backend reads this at startup and the frontend fetches it
from /data/departments on load.
"""

DEPARTMENTS = [
    {
        "name": "Labs",
        "sub_departments": [
            "Coke Oven Lab",
            "BF Lab",
            "Sinter Lab",
            "BPP Lab",
            "SMS Lab",
            "HSM Lab",
        ],
    },
    {
        "name": "Production Units",
        "sub_departments": [
            "Sinter Plant",
            "Coke Oven",
            "BF",
            "SMS (Grade Chemistry)",
            "TSC",
            "HSM (Grade FT & CT)",
        ],
    },
]

DATA_TYPES = [
    {"key": "daily",              "label": "Daily"},
    {"key": "cumulative_to_date", "label": "Cumulative Till Date"},
    {"key": "monthly",            "label": "Monthly"},
    {"key": "month_wise",         "label": "Month-wise"},
    {"key": "cumulative_months",  "label": "Cumulative of Months"},
    {"key": "yearly",             "label": "Yearly"},
]

DATA_TYPE_KEYS = {d["key"] for d in DATA_TYPES}

# Flat lists for quick validation
_ALL_DEPT_NAMES = {d["name"] for d in DEPARTMENTS}
_ALL_SUB_NAMES  = {sub for d in DEPARTMENTS for sub in d["sub_departments"]}


def is_valid_department(name: str) -> bool:
    return name in _ALL_DEPT_NAMES


def is_valid_subdepartment(name_or_dept: str, subdepartment: str = None) -> bool:
    """Accepts either (subdepartment_name,) or (department, subdepartment) call signatures."""
    if subdepartment is None:
        # Called as is_valid_subdepartment(sub_name)
        return name_or_dept in _ALL_SUB_NAMES
    else:
        # Called as is_valid_subdepartment(department, subdepartment)
        department = name_or_dept
        for d in DEPARTMENTS:
            if d["name"] == department:
                return subdepartment in d["sub_departments"]
        return False


def is_valid_data_type(key: str) -> bool:
    return key in DATA_TYPE_KEYS


def slot_key(department: str, subdepartment: str, data_type: str) -> str:
    """Composite key used internally to store / broadcast a specific dataset slot."""
    return f"{department}::{subdepartment}::{data_type}"


def department_list() -> list:
    """Returns the DEPARTMENTS list — used by the /data/departments endpoint."""
    return DEPARTMENTS


def subdepartments_for(department: str) -> list:
    """Returns sub-department names for a given department, or [] if unknown."""
    for d in DEPARTMENTS:
        if d["name"] == department:
            return d["sub_departments"]
    return []
