from datetime import datetime, timezone, date as date_type
from fastapi import APIRouter, Depends, HTTPException, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import Optional

from ..database import get_db
from ..dependencies import get_current_user, require_roles
from ..schemas.leave import (
    LeaveTypeCreate, LeaveTypeUpdate, LeaveTypeOut,
    LeaveRequestCreate, LeaveRequestOut,
    LeaveActionRequest, LeaveBalanceOut, LeaveCalendarItem,
    LeaveBalanceAllocate,
)

router = APIRouter(prefix="/leave", tags=["leave"])

HR_ROLES = ["super_admin", "hr_admin", "hr_manager"]
MANAGER_ROLES = ["super_admin", "hr_admin", "hr_manager", "team_manager"]


async def _build_leave_out(rec: dict, db: AsyncIOMotorDatabase) -> LeaveRequestOut:
    emp = await db.employees.find_one({"_id": rec["employee_id"]})
    lt = await db.leave_types.find_one({"_id": rec["leave_type_id"]})
    return LeaveRequestOut(
        id=str(rec["_id"]),
        employee_id=str(rec["employee_id"]),
        employee_name=emp["full_name"] if emp else "",
        employee_eid=emp["employee_id"] if emp else "",
        leave_type_id=str(rec["leave_type_id"]),
        leave_type_name=lt["name"] if lt else "",
        start_date=date_type.fromisoformat(rec["start_date"]),
        end_date=date_type.fromisoformat(rec["end_date"]),
        total_days=rec["total_days"],
        reason=rec.get("reason", ""),
        status=rec["status"],
        created_at=rec["created_at"],
    )


# ── Leave Types ───────────────────────────────────────────────────────────────

@router.get("/types/", response_model=list[LeaveTypeOut])
async def list_leave_types(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    docs = await db.leave_types.find({}).sort("name", 1).to_list(length=None)
    return [LeaveTypeOut(id=str(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}) for d in docs]


@router.post("/types/", response_model=LeaveTypeOut, status_code=status.HTTP_201_CREATED)
async def create_leave_type(
    payload: LeaveTypeCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(["super_admin", "hr_admin"])),
):
    data = payload.model_dump()
    data["created_at"] = datetime.now(timezone.utc)
    result = await db.leave_types.insert_one(data)
    doc = await db.leave_types.find_one({"_id": result.inserted_id})
    return LeaveTypeOut(id=str(doc["_id"]), **{k: v for k, v in doc.items() if k != "_id"})


@router.delete("/types/{lt_id}")
async def delete_leave_type(
    lt_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(["super_admin", "hr_admin"])),
):
    if not ObjectId.is_valid(lt_id):
        raise HTTPException(status_code=404, detail="Leave type not found")
    await db.leave_types.delete_one({"_id": ObjectId(lt_id)})
    return {"message": "Leave type deleted"}


@router.put("/types/{lt_id}", response_model=LeaveTypeOut)
async def update_leave_type(
    lt_id: str,
    payload: LeaveTypeUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(["super_admin", "hr_admin"])),
):
    if not ObjectId.is_valid(lt_id):
        raise HTTPException(status_code=404, detail="Leave type not found")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    await db.leave_types.update_one({"_id": ObjectId(lt_id)}, {"$set": updates})
    doc = await db.leave_types.find_one({"_id": ObjectId(lt_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Leave type not found")
    return LeaveTypeOut(id=str(doc["_id"]), **{k: v for k, v in doc.items() if k != "_id"})


# ── Leave Balances ────────────────────────────────────────────────────────────

@router.get("/balance/all/", response_model=list[dict])
async def get_all_leave_balances(
    year: Optional[int] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ROLES)),
):
    """HR only — get all employees' leave balances for a year."""
    target_year = year or datetime.now(timezone.utc).year
    balances = await db.leave_balances.find({"year": target_year}).to_list(length=None)
    result = []
    for b in balances:
        emp = await db.employees.find_one({"_id": b["employee_id"]})
        lt = await db.leave_types.find_one({"_id": b["leave_type_id"]})
        result.append({
            "id": str(b["_id"]),
            "employee_id": str(b["employee_id"]),
            "employee_name": emp["full_name"] if emp else "",
            "employee_eid": emp["employee_id"] if emp else "",
            "leave_type_id": str(b["leave_type_id"]),
            "leave_type_name": lt["name"] if lt else "",
            "allocated": b["allocated"],
            "used": b["used"],
            "remaining": b["remaining"],
            "carried_over": b.get("carried_over", 0),
            "year": b["year"],
        })
    return result


@router.post("/balance/allocate/", status_code=status.HTTP_200_OK)
async def allocate_leave_balance(
    payload: LeaveBalanceAllocate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(["super_admin", "hr_admin"])),
):
    """Set / upsert leave balance for an employee for a given year."""
    if not ObjectId.is_valid(payload.employee_id):
        raise HTTPException(status_code=400, detail="Invalid employee_id")
    emp_oid = ObjectId(payload.employee_id)
    stored = []
    for item in payload.allocations:
        if not ObjectId.is_valid(item.leave_type_id):
            continue
        lt_oid = ObjectId(item.leave_type_id)
        total = item.allocated + item.carried_over
        await db.leave_balances.update_one(
            {"employee_id": emp_oid, "leave_type_id": lt_oid, "year": payload.year},
            {"$set": {
                "employee_id": emp_oid,
                "leave_type_id": lt_oid,
                "year": payload.year,
                "allocated": item.allocated,
                "carried_over": item.carried_over,
                "remaining": total,
                "used": 0,
            }},
            upsert=True,
        )
        stored.append(item.leave_type_id)
    return {"message": f"Allocated {len(stored)} leave type(s) for year {payload.year}"}


@router.get("/balance/", response_model=list[LeaveBalanceOut])
async def get_leave_balance(
    employee: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Employees can only see their own balance
    target_employee_id = employee
    if current_user["role"] == "employee":
        emp = await db.employees.find_one({"email": current_user["email"]})
        if not emp:
            return []
        target_employee_id = str(emp["_id"])

    query = {}
    if target_employee_id and ObjectId.is_valid(target_employee_id):
        query["employee_id"] = ObjectId(target_employee_id)
    if year:
        query["year"] = year
    else:
        query["year"] = datetime.now(timezone.utc).year

    balances = await db.leave_balances.find(query).to_list(length=None)
    result = []
    for b in balances:
        lt = await db.leave_types.find_one({"_id": b["leave_type_id"]})
        result.append(LeaveBalanceOut(
            leave_type_id=str(b["leave_type_id"]),
            leave_type_name=lt["name"] if lt else "",
            allocated=b["allocated"],
            used=b["used"],
            remaining=b["remaining"],
            carried_over=b.get("carried_over", 0),
        ))
    return result


# ── Leave Requests ────────────────────────────────────────────────────────────

@router.get("/requests/", response_model=list[LeaveRequestOut])
async def list_leave_requests(
    employee: Optional[str] = Query(None),
    leave_status: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    query = {}
    if current_user["role"] == "employee":
        emp = await db.employees.find_one({"email": current_user["email"]})
        if not emp:
            return []
        query["employee_id"] = emp["_id"]
    elif employee and ObjectId.is_valid(employee):
        query["employee_id"] = ObjectId(employee)

    if leave_status:
        query["status"] = leave_status

    records = await db.leave_requests.find(query).sort("created_at", -1).to_list(length=None)
    return [await _build_leave_out(r, db) for r in records]


@router.post("/requests/", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    payload: LeaveRequestCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Find employee linked to current user
    emp = await db.employees.find_one({"email": current_user["email"]})
    if not emp and current_user["role"] not in ["super_admin", "hr_admin"]:
        raise HTTPException(status_code=400, detail="No employee record linked to your account")

    if not ObjectId.is_valid(payload.leave_type_id):
        raise HTTPException(status_code=404, detail="Leave type not found")
    lt = await db.leave_types.find_one({"_id": ObjectId(payload.leave_type_id)})
    if not lt:
        raise HTTPException(status_code=404, detail="Leave type not found")

    start = payload.start_date
    end = payload.end_date
    if end < start:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")
    if start < date_type.today():
        raise HTTPException(status_code=400, detail="Cannot apply for leave in the past")

    total_days = (end - start).days + 1

    data = {
        "employee_id": emp["_id"] if emp else current_user["_id"],
        "leave_type_id": ObjectId(payload.leave_type_id),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_days": total_days,
        "reason": payload.reason,
        "status": "Pending",
        "manager_action": None,
        "hr_action": None,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.leave_requests.insert_one(data)
    record = await db.leave_requests.find_one({"_id": result.inserted_id})
    return await _build_leave_out(record, db)


@router.patch("/requests/{req_id}/approve")
async def approve_leave(
    req_id: str,
    payload: LeaveActionRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_roles(MANAGER_ROLES)),
):
    if not ObjectId.is_valid(req_id):
        raise HTTPException(status_code=404, detail="Leave request not found")
    rec = await db.leave_requests.find_one({"_id": ObjectId(req_id)})
    if not rec:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if rec["status"] != "Pending":
        raise HTTPException(status_code=400, detail=f"Request is already {rec['status']}")

    action = {"user_id": current_user["_id"], "action": "approved", "comment": payload.comment, "at": datetime.now(timezone.utc)}
    await db.leave_requests.update_one(
        {"_id": rec["_id"]},
        {"$set": {"status": "Approved", "hr_action": action}},
    )
    # Deduct from balance
    year = datetime.now(timezone.utc).year
    await db.leave_balances.update_one(
        {"employee_id": rec["employee_id"], "leave_type_id": rec["leave_type_id"], "year": year},
        {"$inc": {"used": rec["total_days"], "remaining": -rec["total_days"]}},
        upsert=False,
    )
    updated = await db.leave_requests.find_one({"_id": rec["_id"]})
    return await _build_leave_out(updated, db)


@router.patch("/requests/{req_id}/reject")
async def reject_leave(
    req_id: str,
    payload: LeaveActionRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_roles(MANAGER_ROLES)),
):
    if not ObjectId.is_valid(req_id):
        raise HTTPException(status_code=404, detail="Leave request not found")
    rec = await db.leave_requests.find_one({"_id": ObjectId(req_id)})
    if not rec:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if rec["status"] != "Pending":
        raise HTTPException(status_code=400, detail=f"Request is already {rec['status']}")

    action = {"user_id": current_user["_id"], "action": "rejected", "comment": payload.comment, "at": datetime.now(timezone.utc)}
    await db.leave_requests.update_one(
        {"_id": rec["_id"]},
        {"$set": {"status": "Rejected", "hr_action": action}},
    )
    updated = await db.leave_requests.find_one({"_id": rec["_id"]})
    return await _build_leave_out(updated, db)


@router.patch("/requests/{req_id}/cancel")
async def cancel_leave(
    req_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not ObjectId.is_valid(req_id):
        raise HTTPException(status_code=404, detail="Leave request not found")
    rec = await db.leave_requests.find_one({"_id": ObjectId(req_id)})
    if not rec:
        raise HTTPException(status_code=404, detail="Leave request not found")

    # Employees can only cancel their own pending requests
    if current_user["role"] == "employee":
        emp = await db.employees.find_one({"email": current_user["email"]})
        if not emp or rec["employee_id"] != emp["_id"]:
            raise HTTPException(status_code=403, detail="Cannot cancel another employee's leave")

    if rec["status"] not in ["Pending", "Approved"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel a {rec['status']} request")

    # Restore balance if was approved
    if rec["status"] == "Approved":
        year = datetime.now(timezone.utc).year
        await db.leave_balances.update_one(
            {"employee_id": rec["employee_id"], "leave_type_id": rec["leave_type_id"], "year": year},
            {"$inc": {"used": -rec["total_days"], "remaining": rec["total_days"]}},
            upsert=False,
        )

    await db.leave_requests.update_one({"_id": rec["_id"]}, {"$set": {"status": "Cancelled"}})
    return {"message": "Leave request cancelled"}


# ── My Leave Balance (for card grid view) ────────────────────────────────────
@router.get("/my-balance/", response_model=list[LeaveBalanceOut])
async def get_my_leave_balance(
    year: Optional[int] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    emp = await db.employees.find_one({"email": current_user["email"]})
    if not emp:
        return []
    target_year = year or datetime.now(timezone.utc).year
    balances = await db.leave_balances.find(
        {"employee_id": emp["_id"], "year": target_year}
    ).to_list(length=None)
    result = []
    for b in balances:
        lt = await db.leave_types.find_one({"_id": b["leave_type_id"]})
        result.append(LeaveBalanceOut(
            leave_type_id=str(b["leave_type_id"]),
            leave_type_name=lt["name"] if lt else "",
            allocated=b["allocated"],
            used=b["used"],
            remaining=b["remaining"],
            carried_over=b.get("carried_over", 0),
        ))
    return result


# ── Leave Calendar ────────────────────────────────────────────────────────────
@router.get("/calendar/", response_model=list[LeaveCalendarItem])
async def get_leave_calendar(
    month: int = Query(...),
    year: int = Query(...),
    filter_type: str = Query("me", description="me | team"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from datetime import date as dt
    month_start = dt(year, month, 1).isoformat()
    if month == 12:
        month_end = dt(year + 1, 1, 1).isoformat()
    else:
        month_end = dt(year, month + 1, 1).isoformat()

    query = {
        "status": "Approved",
        "start_date": {"$lt": month_end},
        "end_date": {"$gte": month_start},
    }

    if filter_type == "me":
        emp = await db.employees.find_one({"email": current_user["email"]})
        if emp:
            query["employee_id"] = emp["_id"]
        else:
            return []

    records = await db.leave_requests.find(query).sort("start_date", 1).to_list(length=None)
    result = []
    for r in records:
        emp = await db.employees.find_one({"_id": r["employee_id"]})
        lt = await db.leave_types.find_one({"_id": r["leave_type_id"]})
        result.append(LeaveCalendarItem(
            employee_name=emp["full_name"] if emp else "",
            employee_eid=emp["employee_id"] if emp else "",
            leave_type_name=lt["name"] if lt else "",
            start_date=dt.fromisoformat(r["start_date"]),
            end_date=dt.fromisoformat(r["end_date"]),
            total_days=r["total_days"],
            status=r["status"],
        ))
    return result
