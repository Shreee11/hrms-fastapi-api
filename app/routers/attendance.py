from datetime import date as date_type, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import Optional

from ..database import get_db
from ..dependencies import get_current_user
from ..schemas import AttendanceCreate, AttendanceUpdate, AttendanceOut

router = APIRouter(prefix="/attendance", tags=["attendance"])


async def _get_attendance_or_404(attendance_id: str, db: AsyncIOMotorDatabase) -> dict:
    if not ObjectId.is_valid(attendance_id):
        raise HTTPException(status_code=404, detail="Attendance record not found")
    doc = await db.attendance.find_one({"_id": ObjectId(attendance_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return doc


async def _build_attendance_out(record: dict, db: AsyncIOMotorDatabase) -> AttendanceOut:
    emp = await db.employees.find_one({"_id": record["employee_id"]})
    return AttendanceOut(
        id=str(record["_id"]),
        employee_id=str(record["employee_id"]),
        employee_name=emp["full_name"] if emp else "",
        employee_eid=emp["employee_id"] if emp else "",
        date=date_type.fromisoformat(record["date"]),
        status=record["status"],
        created_at=record["created_at"],
    )


@router.get("/", response_model=list[AttendanceOut])
async def list_attendance(
    employee: Optional[str] = Query(None),
    date: Optional[date_type] = Query(None),
    date_from: Optional[date_type] = Query(None),
    date_to: Optional[date_type] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    query = {}
    if employee:
        if not ObjectId.is_valid(employee):
            return []
        query["employee_id"] = ObjectId(employee)
    if date:
        query["date"] = date.isoformat()
    else:
        date_query = {}
        if date_from:
            date_query["$gte"] = date_from.isoformat()
        if date_to:
            date_query["$lte"] = date_to.isoformat()
        if date_query:
            query["date"] = date_query
    records = await db.attendance.find(query).sort("date", -1).to_list(length=None)
    return [await _build_attendance_out(r, db) for r in records]


@router.post("/", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
async def create_attendance(
    payload: AttendanceCreate, db: AsyncIOMotorDatabase = Depends(get_db)
):
    if not ObjectId.is_valid(payload.employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    emp_oid = ObjectId(payload.employee_id)
    if not await db.employees.find_one({"_id": emp_oid}):
        raise HTTPException(status_code=404, detail="Employee not found")
    date_str = payload.date.isoformat()
    if await db.attendance.find_one({"employee_id": emp_oid, "date": date_str}):
        raise HTTPException(
            status_code=400,
            detail="Attendance for this employee on this date already exists.",
        )
    data = {
        "employee_id": emp_oid,
        "date": date_str,
        "status": payload.status,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.attendance.insert_one(data)
    record = await db.attendance.find_one({"_id": result.inserted_id})
    return await _build_attendance_out(record, db)


@router.put("/{attendance_id}", response_model=AttendanceOut)
async def update_attendance(
    attendance_id: str, payload: AttendanceUpdate, db: AsyncIOMotorDatabase = Depends(get_db)
):
    record = await _get_attendance_or_404(attendance_id, db)
    a_oid = record["_id"]
    if not ObjectId.is_valid(payload.employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    emp_oid = ObjectId(payload.employee_id)
    if not await db.employees.find_one({"_id": emp_oid}):
        raise HTTPException(status_code=404, detail="Employee not found")
    date_str = payload.date.isoformat()
    if await db.attendance.find_one({
        "employee_id": emp_oid,
        "date": date_str,
        "_id": {"$ne": a_oid},
    }):
        raise HTTPException(
            status_code=400,
            detail="Attendance for this employee on this date already exists.",
        )
    await db.attendance.update_one(
        {"_id": a_oid},
        {"$set": {"employee_id": emp_oid, "date": date_str, "status": payload.status}},
    )
    updated = await db.attendance.find_one({"_id": a_oid})
    return await _build_attendance_out(updated, db)


@router.delete("/{attendance_id}")
async def delete_attendance(attendance_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    record = await _get_attendance_or_404(attendance_id, db)
    await db.attendance.delete_one({"_id": record["_id"]})
    return {"message": "Attendance record deleted successfully."}


# ── Self-service clock-in / clock-out ────────────────────────────────────────

@router.get("/my/today")
async def my_today(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    emp = await db.employees.find_one({"email": current_user["email"]})
    if not emp:
        return {"status": "no_employee", "clock_in": None, "clock_out": None, "attendance_id": None}
    today = date_type.today().isoformat()
    record = await db.attendance.find_one({"employee_id": emp["_id"], "date": today})
    if not record:
        return {"status": "not_clocked_in", "clock_in": None, "clock_out": None, "attendance_id": None}
    status_val = "clocked_out" if record.get("clock_out") else "clocked_in"
    return {
        "status": status_val,
        "clock_in": record.get("clock_in"),
        "clock_out": record.get("clock_out"),
        "attendance_id": str(record["_id"]),
    }


@router.post("/my/clock-in")
async def clock_in(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    emp = await db.employees.find_one({"email": current_user["email"]})
    if not emp:
        raise HTTPException(status_code=400, detail="No employee record linked to your account.")
    today = date_type.today().isoformat()
    if await db.attendance.find_one({"employee_id": emp["_id"], "date": today}):
        raise HTTPException(status_code=400, detail="Already clocked in today.")
    now = datetime.now(timezone.utc)
    await db.attendance.insert_one({
        "employee_id": emp["_id"],
        "date": today,
        "status": "Present",
        "clock_in": now,
        "clock_out": None,
        "created_at": now,
    })
    return {"message": "Clocked in successfully", "clock_in": now}


@router.post("/my/clock-out")
async def clock_out(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    emp = await db.employees.find_one({"email": current_user["email"]})
    if not emp:
        raise HTTPException(status_code=400, detail="No employee record linked to your account.")
    today = date_type.today().isoformat()
    record = await db.attendance.find_one({"employee_id": emp["_id"], "date": today})
    if not record:
        raise HTTPException(status_code=400, detail="You have not clocked in today.")
    if record.get("clock_out"):
        raise HTTPException(status_code=400, detail="Already clocked out today.")
    now = datetime.now(timezone.utc)
    await db.attendance.update_one(
        {"_id": record["_id"]},
        {"$set": {"clock_out": now}},
    )
    return {"message": "Clocked out successfully", "clock_out": now}


@router.get("/my/history")
async def my_history(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    emp = await db.employees.find_one({"email": current_user["email"]})
    if not emp:
        return []
    query = {"employee_id": emp["_id"]}
    if month and year:
        prefix = f"{year}-{str(month).zfill(2)}"
        query["date"] = {"$regex": f"^{prefix}"}
    records = await db.attendance.find(query).sort("date", 1).to_list(length=None)
    return [
        {
            "id": str(r["_id"]),
            "date": r["date"],
            "status": r["status"],
            "clock_in": r.get("clock_in"),
            "clock_out": r.get("clock_out"),
        }
        for r in records
    ]
