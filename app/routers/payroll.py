from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import Optional
import calendar

from ..database import get_db
from ..dependencies import get_current_user, require_roles
from ..schemas.payroll import (
    SalaryStructureCreate, SalaryStructureOut,
    PayrollRunCreate, PayrollRunOut,
    PayslipOut, SalaryHistoryOut,
)

router = APIRouter(prefix="/payroll", tags=["payroll"])

HR_ADMIN_ROLES = ["super_admin", "hr_admin"]


async def _build_salary_out(doc: dict, db: AsyncIOMotorDatabase) -> SalaryStructureOut:
    emp = await db.employees.find_one({"_id": doc["employee_id"]})
    gross = (doc["basic"] + doc["hra"] + doc.get("da", 0) + doc.get("ta", 0)
             + doc.get("special_allowance", 0) + doc.get("medical_allowance", 0)
             + doc.get("other_allowances", 0))
    net = (gross - doc["pf_deduction"] - doc.get("esi", 0)
           - doc.get("professional_tax", 0) - doc.get("tds", 0)
           - doc.get("other_deductions", 0))
    return SalaryStructureOut(
        id=str(doc["_id"]),
        employee_id=str(doc["employee_id"]),
        employee_name=emp["full_name"] if emp else "",
        employee_eid=emp["employee_id"] if emp else "",
        basic=doc["basic"],
        hra=doc["hra"],
        da=doc.get("da", 0.0),
        ta=doc.get("ta", 0.0),
        special_allowance=doc.get("special_allowance", 0.0),
        medical_allowance=doc.get("medical_allowance", 0.0),
        other_allowances=doc.get("other_allowances", 0.0),
        gross_salary=gross,
        pf_deduction=doc["pf_deduction"],
        esi=doc.get("esi", 0.0),
        professional_tax=doc.get("professional_tax", 0.0),
        tds=doc.get("tds", 0.0),
        other_deductions=doc.get("other_deductions", 0.0),
        net_salary=net,
        bank_name=doc.get("bank_name", ""),
        account_number=doc.get("account_number", ""),
        ifsc_code=doc.get("ifsc_code", ""),
        pan_number=doc.get("pan_number", ""),
        effective_from=doc["effective_from"],
        created_at=doc["created_at"],
    )


# ── Salary Structures ─────────────────────────────────────────────────────────

@router.get("/salary-structures/", response_model=list[SalaryStructureOut])
async def list_salary_structures(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in HR_ADMIN_ROLES:
        # Employee sees only their own — match by email
        emp = await db.employees.find_one({"email": current_user["email"]})
        if not emp:
            return []
        docs = await db.salary_structures.find({"employee_id": emp["_id"]}).sort("effective_from", -1).to_list(length=None)
    else:
        docs = await db.salary_structures.find({}).sort("effective_from", -1).to_list(length=None)
    return [await _build_salary_out(d, db) for d in docs]


@router.post("/salary-structures/", response_model=SalaryStructureOut, status_code=status.HTTP_201_CREATED)
async def create_salary_structure(
    payload: SalaryStructureCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ADMIN_ROLES)),
):
    if not ObjectId.is_valid(payload.employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    emp_oid = ObjectId(payload.employee_id)
    if not await db.employees.find_one({"_id": emp_oid}):
        raise HTTPException(status_code=404, detail="Employee not found")

    now = datetime.now(timezone.utc)
    data = {
        "employee_id": emp_oid,
        "basic": payload.basic,
        "hra": payload.hra,
        "da": payload.da,
        "ta": payload.ta,
        "special_allowance": payload.special_allowance,
        "medical_allowance": payload.medical_allowance,
        "other_allowances": payload.other_allowances,
        "pf_deduction": payload.pf_deduction,
        "esi": payload.esi,
        "professional_tax": payload.professional_tax,
        "tds": payload.tds,
        "other_deductions": payload.other_deductions,
        "bank_name": payload.bank_name,
        "account_number": payload.account_number,
        "ifsc_code": payload.ifsc_code,
        "pan_number": payload.pan_number,
        "effective_from": now,
        "created_at": now,
    }
    result = await db.salary_structures.insert_one(data)
    doc = await db.salary_structures.find_one({"_id": result.inserted_id})
    return await _build_salary_out(doc, db)


@router.put("/salary-structures/{struct_id}", response_model=SalaryStructureOut)
async def update_salary_structure(
    struct_id: str,
    payload: SalaryStructureCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ADMIN_ROLES)),
):
    if not ObjectId.is_valid(struct_id):
        raise HTTPException(status_code=404, detail="Salary structure not found")
    oid = ObjectId(struct_id)
    existing = await db.salary_structures.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Salary structure not found")

    # ── Save snapshot of current values as history ─────────────────────────
    old_gross = (existing["basic"] + existing["hra"] + existing.get("da", 0)
                 + existing.get("ta", 0) + existing.get("special_allowance", 0)
                 + existing.get("medical_allowance", 0) + existing.get("other_allowances", 0))
    old_net = (old_gross - existing["pf_deduction"] - existing.get("esi", 0)
               - existing.get("professional_tax", 0) - existing.get("tds", 0)
               - existing.get("other_deductions", 0))
    await db.salary_history.insert_one({
        "structure_id": oid,
        "changed_at": datetime.now(timezone.utc),
        "basic": existing["basic"],
        "hra": existing["hra"],
        "da": existing.get("da", 0.0),
        "ta": existing.get("ta", 0.0),
        "special_allowance": existing.get("special_allowance", 0.0),
        "medical_allowance": existing.get("medical_allowance", 0.0),
        "other_allowances": existing.get("other_allowances", 0.0),
        "gross_salary": old_gross,
        "pf_deduction": existing["pf_deduction"],
        "esi": existing.get("esi", 0.0),
        "professional_tax": existing.get("professional_tax", 0.0),
        "tds": existing.get("tds", 0.0),
        "other_deductions": existing.get("other_deductions", 0.0),
        "net_salary": old_net,
    })

    emp_oid = ObjectId(payload.employee_id) if ObjectId.is_valid(payload.employee_id) else None
    update = {
        "basic": payload.basic, "hra": payload.hra,
        "da": payload.da, "ta": payload.ta,
        "special_allowance": payload.special_allowance,
        "medical_allowance": payload.medical_allowance,
        "other_allowances": payload.other_allowances,
        "pf_deduction": payload.pf_deduction,
        "esi": payload.esi, "professional_tax": payload.professional_tax,
        "tds": payload.tds, "other_deductions": payload.other_deductions,
        "bank_name": payload.bank_name, "account_number": payload.account_number,
        "ifsc_code": payload.ifsc_code, "pan_number": payload.pan_number,
        "effective_from": datetime.now(timezone.utc),
    }
    if emp_oid:
        update["employee_id"] = emp_oid
    await db.salary_structures.update_one({"_id": oid}, {"$set": update})
    doc = await db.salary_structures.find_one({"_id": oid})
    return await _build_salary_out(doc, db)


@router.get("/salary-structures/{struct_id}/history", response_model=list[SalaryHistoryOut])
async def get_salary_history(
    struct_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ADMIN_ROLES)),
):
    if not ObjectId.is_valid(struct_id):
        raise HTTPException(status_code=404, detail="Salary structure not found")
    docs = await db.salary_history.find(
        {"structure_id": ObjectId(struct_id)}
    ).sort("changed_at", -1).to_list(length=None)
    return [SalaryHistoryOut(
        id=str(d["_id"]),
        structure_id=str(d["structure_id"]),
        changed_at=d["changed_at"],
        basic=d["basic"], hra=d["hra"],
        da=d.get("da", 0.0), ta=d.get("ta", 0.0),
        special_allowance=d.get("special_allowance", 0.0),
        medical_allowance=d.get("medical_allowance", 0.0),
        other_allowances=d.get("other_allowances", 0.0),
        gross_salary=d["gross_salary"],
        pf_deduction=d["pf_deduction"],
        esi=d.get("esi", 0.0),
        professional_tax=d.get("professional_tax", 0.0),
        tds=d.get("tds", 0.0),
        other_deductions=d.get("other_deductions", 0.0),
        net_salary=d["net_salary"],
    ) for d in docs]


# ── Payroll Runs ──────────────────────────────────────────────────────────────

@router.get("/runs/", response_model=list[PayrollRunOut])
async def list_payroll_runs(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ADMIN_ROLES)),
):
    docs = await db.payroll_runs.find({}).sort("created_at", -1).to_list(length=None)
    return [PayrollRunOut(
        id=str(d["_id"]), month=d["month"], year=d["year"],
        status=d["status"], total_cost=d["total_cost"],
        created_at=d["created_at"], approved_at=d.get("approved_at"),
    ) for d in docs]


@router.post("/runs/", response_model=PayrollRunOut, status_code=status.HTTP_201_CREATED)
async def create_payroll_run(
    payload: PayrollRunCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_roles(HR_ADMIN_ROLES)),
):
    # Prevent duplicate run for same month/year
    if await db.payroll_runs.find_one({"month": payload.month, "year": payload.year}):
        raise HTTPException(status_code=400, detail="Payroll for this month/year already exists")

    # Fetch all active employees who have a salary structure
    employees = await db.employees.find({"status": "Active"}).to_list(length=None)
    total_cost = 0.0
    payslips = []

    # Days in the month
    days_in_month = calendar.monthrange(payload.year, payload.month)[1]

    for emp in employees:
        # Latest salary structure
        struct = await db.salary_structures.find_one(
            {"employee_id": emp["_id"]},
            sort=[("effective_from", -1)],
        )
        if not struct:
            continue

        # Count present / absent days
        month_str_prefix = f"{payload.year}-{str(payload.month).zfill(2)}"
        days_present = await db.attendance.count_documents({
            "employee_id": emp["_id"],
            "status": "Present",
            "date": {"$regex": f"^{month_str_prefix}"},
        })
        days_absent = days_in_month - days_present

        gross = (struct["basic"] + struct["hra"] + struct.get("da", 0)
                 + struct.get("ta", 0) + struct.get("special_allowance", 0)
                 + struct.get("medical_allowance", 0) + struct.get("other_allowances", 0))
        deductions = (struct["pf_deduction"] + struct.get("esi", 0)
                      + struct.get("professional_tax", 0) + struct.get("tds", 0)
                      + struct.get("other_deductions", 0))
        net = gross - deductions

        total_cost += net
        payslips.append({
            "employee_id": emp["_id"],
            "month": payload.month,
            "year": payload.year,
            "basic": struct["basic"],
            "hra": struct["hra"],
            "da": struct.get("da", 0),
            "ta": struct.get("ta", 0),
            "special_allowance": struct.get("special_allowance", 0),
            "medical_allowance": struct.get("medical_allowance", 0),
            "other_allowances": struct.get("other_allowances", 0),
            "gross": gross,
            "pf": struct["pf_deduction"],
            "esi": struct.get("esi", 0),
            "professional_tax": struct.get("professional_tax", 0),
            "tds": struct.get("tds", 0),
            "other_deductions": struct.get("other_deductions", 0),
            "net": net,
            "days_present": days_present,
            "days_absent": days_absent,
            "created_at": datetime.now(timezone.utc),
        })

    now = datetime.now(timezone.utc)
    run_data = {
        "month": payload.month,
        "year": payload.year,
        "status": "Draft",
        "run_by": current_user["_id"],
        "total_cost": total_cost,
        "created_at": now,
        "approved_at": None,
    }
    run_result = await db.payroll_runs.insert_one(run_data)
    run_id = run_result.inserted_id

    if payslips:
        for ps in payslips:
            ps["payroll_run_id"] = run_id
        await db.payslips.insert_many(payslips)

    doc = await db.payroll_runs.find_one({"_id": run_id})
    return PayrollRunOut(
        id=str(doc["_id"]), month=doc["month"], year=doc["year"],
        status=doc["status"], total_cost=doc["total_cost"],
        created_at=doc["created_at"], approved_at=doc.get("approved_at"),
    )


@router.patch("/runs/{run_id}/approve")
async def approve_payroll_run(
    run_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ADMIN_ROLES)),
):
    if not ObjectId.is_valid(run_id):
        raise HTTPException(status_code=404, detail="Payroll run not found")
    oid = ObjectId(run_id)
    doc = await db.payroll_runs.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if doc["status"] != "Draft":
        raise HTTPException(status_code=400, detail="Only Draft runs can be approved")
    now = datetime.now(timezone.utc)
    await db.payroll_runs.update_one({"_id": oid}, {"$set": {"status": "Approved", "approved_at": now}})
    doc = await db.payroll_runs.find_one({"_id": oid})
    return PayrollRunOut(
        id=str(doc["_id"]), month=doc["month"], year=doc["year"],
        status=doc["status"], total_cost=doc["total_cost"],
        created_at=doc["created_at"], approved_at=doc.get("approved_at"),
    )


@router.patch("/runs/{run_id}/mark-paid")
async def mark_payroll_run_paid(
    run_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ADMIN_ROLES)),
):
    if not ObjectId.is_valid(run_id):
        raise HTTPException(status_code=404, detail="Payroll run not found")
    oid = ObjectId(run_id)
    doc = await db.payroll_runs.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if doc["status"] != "Approved":
        raise HTTPException(status_code=400, detail="Only Approved runs can be marked as Paid")
    await db.payroll_runs.update_one({"_id": oid}, {"$set": {"status": "Paid"}})
    doc = await db.payroll_runs.find_one({"_id": oid})
    return PayrollRunOut(
        id=str(doc["_id"]), month=doc["month"], year=doc["year"],
        status=doc["status"], total_cost=doc["total_cost"],
        created_at=doc["created_at"], approved_at=doc.get("approved_at"),
    )


# ── Payslips ──────────────────────────────────────────────────────────────────

@router.get("/payslips/", response_model=list[PayslipOut])
async def list_payslips(
    run_id: Optional[str] = Query(None),
    employee: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    query = {}
    if current_user["role"] not in HR_ADMIN_ROLES:
        # Non-admin sees only their own payslips — match by email
        emp = await db.employees.find_one({"email": current_user["email"]})
        if not emp:
            return []
        query["employee_id"] = emp["_id"]
    elif employee and ObjectId.is_valid(employee):
        query["employee_id"] = ObjectId(employee)

    if run_id and ObjectId.is_valid(run_id):
        query["payroll_run_id"] = ObjectId(run_id)

    docs = await db.payslips.find(query).sort("created_at", -1).to_list(length=None)
    result = []
    for d in docs:
        emp = await db.employees.find_one({"_id": d["employee_id"]})
        result.append(PayslipOut(
            id=str(d["_id"]),
            payroll_run_id=str(d["payroll_run_id"]),
            employee_id=str(d["employee_id"]),
            employee_name=emp["full_name"] if emp else "",
            employee_eid=emp["employee_id"] if emp else "",
            month=d["month"], year=d["year"],
            basic=d["basic"], hra=d["hra"],
            da=d.get("da", 0), ta=d.get("ta", 0),
            special_allowance=d.get("special_allowance", 0),
            medical_allowance=d.get("medical_allowance", 0),
            other_allowances=d.get("other_allowances", 0),
            gross=d["gross"],
            pf=d["pf"],
            esi=d.get("esi", 0),
            professional_tax=d.get("professional_tax", 0),
            tds=d.get("tds", 0),
            other_deductions=d.get("other_deductions", 0),
            net=d["net"], days_present=d["days_present"], days_absent=d["days_absent"],
            created_at=d["created_at"],
        ))
    return result
