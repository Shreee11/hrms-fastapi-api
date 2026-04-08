from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DepartmentCreate(BaseModel):
    name: str
    head_id: Optional[str] = None  # employee ObjectId string


class DepartmentOut(BaseModel):
    id: str
    name: str
    head_id: Optional[str] = None
    head_name: Optional[str] = None
    employee_count: int = 0
    created_at: datetime


class DesignationCreate(BaseModel):
    title: str
    department_id: Optional[str] = None
    salary_grade: Optional[str] = None


class DesignationOut(BaseModel):
    id: str
    title: str
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    salary_grade: Optional[str] = None
    created_at: datetime
