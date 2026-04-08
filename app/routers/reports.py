from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from datetime import datetime, timezone

from ..database import get_db
from ..dependencies import require_roles

router = APIRouter(prefix="/reports", tags=["reports"])

HR_ROLES = ["super_admin", "hr_admin", "hr_manager"]
HR_ADMIN_ROLES = ["super_admin", "hr_admin"]


@router.get("/headcount")
async def headcount_report(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ROLES)),
):
    total = await db.employees.count_documents({"status": "Active"})
    inactive = await db.employees.count_documents({"status": "Inactive"})
    terminated = await db.employees.count_documents({"status": "Terminated"})

    dept_pipeline = [
        {"$match": {"status": "Active"}},
        {"$group": {"_id": "$department", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    dept_docs = await db.employees.aggregate(dept_pipeline).to_list(length=None)

    type_pipeline = [
        {"$match": {"status": "Active"}},
        {"$group": {"_id": "$employment_type", "count": {"$sum": 1}}},
    ]
    type_docs = await db.employees.aggregate(type_pipeline).to_list(length=None)

    return {
        "total_active": total,
        "total_inactive": inactive,
        "total_terminated": terminated,
        "by_department": [{"department": d["_id"] or "Unassigned", "count": d["count"]} for d in dept_docs],
        "by_employment_type": [{"type": d["_id"] or "Unknown", "count": d["count"]} for d in type_docs],
    }


@router.get("/attendance")
async def attendance_report(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ROLES)),
):
    att_query = {}
    if date_from:
        att_query.setdefault("date", {})["$gte"] = date_from
    if date_to:
        att_query.setdefault("date", {})["$lte"] = date_to

    total_records = await db.attendance.count_documents(att_query)
    present = await db.attendance.count_documents({**att_query, "status": "Present"})
    absent = await db.attendance.count_documents({**att_query, "status": "Absent"})
    wfh = await db.attendance.count_documents({**att_query, "status": "WFH"})
    half_day = await db.attendance.count_documents({**att_query, "status": "Half-Day"})

    present_pct = round((present / total_records * 100), 1) if total_records else 0

    return {
        "total_records": total_records,
        "present": present,
        "absent": absent,
        "wfh": wfh,
        "half_day": half_day,
        "present_percentage": present_pct,
    }


@router.get("/leave")
async def leave_report(
    year: Optional[int] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ROLES)),
):
    query = {}
    if year:
        query["$expr"] = {"$eq": [{"$year": "$created_at"}, year]}

    total = await db.leave_requests.count_documents(query)
    approved = await db.leave_requests.count_documents({**query, "status": "Approved"})
    rejected = await db.leave_requests.count_documents({**query, "status": "Rejected"})
    pending = await db.leave_requests.count_documents({**query, "status": "Pending"})

    type_pipeline = [
        {"$match": {"status": "Approved"}},
        {"$group": {"_id": "$leave_type_id", "total_days": {"$sum": "$total_days"}, "count": {"$sum": 1}}},
        {"$sort": {"total_days": -1}},
    ]
    type_docs = await db.leave_requests.aggregate(type_pipeline).to_list(length=None)
    by_type = []
    for t in type_docs:
        lt = await db.leave_types.find_one({"_id": t["_id"]})
        by_type.append({"leave_type": lt["name"] if lt else "Unknown", "total_days": t["total_days"], "count": t["count"]})

    return {
        "total_requests": total,
        "approved": approved,
        "rejected": rejected,
        "pending": pending,
        "by_leave_type": by_type,
    }


@router.get("/payroll")
async def payroll_report(
    year: Optional[int] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ADMIN_ROLES)),
):
    query = {}
    if year:
        query["year"] = year

    runs = await db.payroll_runs.find(query).sort("year", 1).to_list(length=None)
    monthly = [{"month": r["month"], "year": r["year"], "total_cost": r["total_cost"], "status": r["status"]} for r in runs]
    total_cost = sum(r["total_cost"] for r in runs if r["status"] in ["Approved", "Paid"])

    return {
        "total_cost_ytd": total_cost,
        "monthly_breakdown": monthly,
    }


@router.get("/turnover")
async def turnover_report(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ADMIN_ROLES)),
):
    query = {"status": "Terminated"}
    if date_from or date_to:
        date_q = {}
        if date_from:
            date_q["$gte"] = date_from
        if date_to:
            date_q["$lte"] = date_to
        # end_date is stored as ISODate on employees
        if date_q:
            query["end_date"] = date_q

    terminated_employees = await db.employees.find(query).to_list(length=None)
    total_active = await db.employees.count_documents({"status": "Active"})
    turnover_rate = round(len(terminated_employees) / (total_active + len(terminated_employees)) * 100, 1) if (total_active + len(terminated_employees)) > 0 else 0

    return {
        "terminated_count": len(terminated_employees),
        "active_count": total_active,
        "turnover_rate_percent": turnover_rate,
        "terminated_employees": [
            {
                "employee_id": e.get("employee_id"),
                "full_name": e.get("full_name"),
                "department": e.get("department"),
                "end_date": e.get("end_date").isoformat() if e.get("end_date") else None,
            }
            for e in terminated_employees
        ],
    }
