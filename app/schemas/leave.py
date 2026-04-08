from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel


class LeaveTypeCreate(BaseModel):
    name: str
    days_per_year: int
    is_paid: bool = True
    carry_forward: bool = False
    max_carry: int = 0


class LeaveTypeUpdate(BaseModel):
    name: Optional[str] = None
    days_per_year: Optional[int] = None
    is_paid: Optional[bool] = None
    carry_forward: Optional[bool] = None
    max_carry: Optional[int] = None


class LeaveAllocationItem(BaseModel):
    leave_type_id: str
    allocated: int
    carried_over: int = 0


class LeaveBalanceAllocate(BaseModel):
    employee_id: str
    year: int
    allocations: List[LeaveAllocationItem]


class LeaveTypeOut(LeaveTypeCreate):
    id: str
    created_at: datetime


class LeaveRequestCreate(BaseModel):
    leave_type_id: str
    start_date: date
    end_date: date
    reason: str


class LeaveRequestOut(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    employee_eid: str
    leave_type_id: str
    leave_type_name: str
    start_date: date
    end_date: date
    total_days: int
    reason: str
    status: str
    created_at: datetime


class LeaveActionRequest(BaseModel):
    comment: Optional[str] = ""


class LeaveBalanceOut(BaseModel):
    leave_type_id: str
    leave_type_name: str
    allocated: int
    used: int
    remaining: int
    carried_over: int


class LeaveCalendarItem(BaseModel):
    employee_name: str
    employee_eid: str
    leave_type_name: str
    start_date: date
    end_date: date
    total_days: int
    status: str
