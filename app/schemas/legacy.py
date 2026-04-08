"""Legacy schemas for employees and attendance — preserved for backward compatibility."""
from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, field_validator
from pydantic_core import core_schema
from bson import ObjectId


class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return str(v)
        raise ValueError(f"Invalid ObjectId: {v}")


# ── Employee ────────────────────────────────────────────────────────────────

class EmployeeBase(BaseModel):
    employee_id: str
    full_name: str
    email: EmailStr
    department: str

    @field_validator("employee_id")
    @classmethod
    def employee_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("employee_id cannot be blank")
        return v.strip()

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("full_name cannot be blank")
        return v.strip()

    @field_validator("department")
    @classmethod
    def department_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("department cannot be blank")
        return v.strip()


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(EmployeeBase):
    pass


class EmployeeOut(EmployeeBase):
    id: str
    created_at: datetime
    total_present: int = 0

    model_config = {"from_attributes": True}


# ── Attendance ───────────────────────────────────────────────────────────────

class AttendanceBase(BaseModel):
    employee_id: str
    date: date
    status: Literal["Present", "Absent"]

    @field_validator("date")
    @classmethod
    def date_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Cannot mark attendance for a future date")
        return v


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(AttendanceBase):
    pass


class AttendanceOut(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    employee_eid: str
    date: date
    status: str
    created_at: datetime


# ── Dashboard ────────────────────────────────────────────────────────────────

class DepartmentCount(BaseModel):
    department: str
    count: int


class DashboardOut(BaseModel):
    total_employees: int
    total_departments: int
    department_counts: list[DepartmentCount]
