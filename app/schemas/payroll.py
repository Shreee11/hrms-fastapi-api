from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SalaryStructureCreate(BaseModel):
    employee_id: str
    # Earnings
    basic: float
    hra: float = 0.0
    da: float = 0.0
    ta: float = 0.0
    special_allowance: float = 0.0
    medical_allowance: float = 0.0
    other_allowances: float = 0.0
    # Deductions
    pf_deduction: float = 0.0
    esi: float = 0.0
    professional_tax: float = 0.0
    tds: float = 0.0
    other_deductions: float = 0.0
    # Bank Details
    bank_name: str = ""
    account_number: str = ""
    ifsc_code: str = ""
    pan_number: str = ""


class SalaryStructureOut(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    employee_eid: str
    # Earnings
    basic: float
    hra: float
    da: float
    ta: float
    special_allowance: float
    medical_allowance: float
    other_allowances: float
    gross_salary: float
    # Deductions
    pf_deduction: float
    esi: float
    professional_tax: float
    tds: float
    other_deductions: float
    net_salary: float
    # Bank Details
    bank_name: str
    account_number: str
    ifsc_code: str
    pan_number: str
    effective_from: datetime
    created_at: datetime


class PayrollRunCreate(BaseModel):
    month: int
    year: int


class PayrollRunOut(BaseModel):
    id: str
    month: int
    year: int
    status: str
    total_cost: float
    created_at: datetime
    approved_at: Optional[datetime] = None


class PayslipOut(BaseModel):
    id: str
    payroll_run_id: str
    employee_id: str
    employee_name: str
    employee_eid: str
    month: int
    year: int
    # Earnings
    basic: float
    hra: float
    da: float = 0.0
    ta: float = 0.0
    special_allowance: float = 0.0
    medical_allowance: float = 0.0
    other_allowances: float = 0.0
    gross: float
    # Deductions
    pf: float
    esi: float = 0.0
    professional_tax: float = 0.0
    tds: float = 0.0
    other_deductions: float = 0.0
    net: float
    days_present: int
    days_absent: int
    created_at: datetime


class SalaryHistoryOut(BaseModel):
    id: str
    structure_id: str
    changed_at: datetime
    basic: float
    hra: float
    da: float
    ta: float
    special_allowance: float
    medical_allowance: float
    other_allowances: float
    gross_salary: float
    pf_deduction: float
    esi: float
    professional_tax: float
    tds: float
    other_deductions: float
    net_salary: float
