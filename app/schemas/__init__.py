# app/schemas/__init__.py
# Re-export legacy schemas so existing routers keep working
from .legacy import (
    PyObjectId,
    EmployeeBase, EmployeeCreate, EmployeeUpdate, EmployeeOut,
    AttendanceBase, AttendanceCreate, AttendanceUpdate, AttendanceOut,
    DepartmentCount, DashboardOut,
)

__all__ = [
    "PyObjectId",
    "EmployeeBase", "EmployeeCreate", "EmployeeUpdate", "EmployeeOut",
    "AttendanceBase", "AttendanceCreate", "AttendanceUpdate", "AttendanceOut",
    "DepartmentCount", "DashboardOut",
]
