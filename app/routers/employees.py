from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import Optional

from ..database import get_db
from ..models import serialize_doc
from ..schemas import (
    EmployeeCreate, EmployeeUpdate, EmployeeOut, DashboardOut, DepartmentCount
)

router = APIRouter(prefix="/employees", tags=["employees"])


async def _get_employee_or_404(employee_id: str, db: AsyncIOMotorDatabase) -> dict:
    if not ObjectId.is_valid(employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    doc = await db.employees.find_one({"_id": ObjectId(employee_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Employee not found")
    return doc


async def _build_employee_out(doc: dict, db: AsyncIOMotorDatabase) -> EmployeeOut:
    total_present = await db.attendance.count_documents(
        {"employee_id": doc["_id"], "status": "Present"}
    )
    d = serialize_doc(doc)
    d["total_present"] = total_present
    return EmployeeOut(**d)


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(db: AsyncIOMotorDatabase = Depends(get_db)):
    total_employees = await db.employees.count_documents({})
    pipeline = [{"$group": {"_id": "$department", "count": {"$sum": 1}}}]
    dept_docs = await db.employees.aggregate(pipeline).to_list(length=None)
    department_counts = sorted(
        [DepartmentCount(department=d["_id"], count=d["count"]) for d in dept_docs],
        key=lambda x: x.count,
        reverse=True,
    )
    return DashboardOut(
        total_employees=total_employees,
        total_departments=len(department_counts),
        department_counts=department_counts,
    )


@router.get("/", response_model=list[EmployeeOut])
async def list_employees(
    search: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    query = {}
    if search:
        pattern = {"$regex": search, "$options": "i"}
        query = {"$or": [
            {"full_name": pattern},
            {"employee_id": pattern},
            {"department": pattern},
        ]}
    docs = await db.employees.find(query).sort("created_at", -1).to_list(length=None)
    return [await _build_employee_out(doc, db) for doc in docs]


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(employee_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await _get_employee_or_404(employee_id, db)
    return await _build_employee_out(doc, db)


@router.post("/", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(payload: EmployeeCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    if await db.employees.find_one({"employee_id": payload.employee_id}):
        raise HTTPException(status_code=400, detail="An employee with this ID already exists.")
    if await db.employees.find_one({"email": payload.email}):
        raise HTTPException(status_code=400, detail="An employee with this email already exists.")
    data = payload.model_dump()
    data["created_at"] = datetime.now(timezone.utc)
    result = await db.employees.insert_one(data)
    doc = await db.employees.find_one({"_id": result.inserted_id})
    return await _build_employee_out(doc, db)


@router.put("/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: str, payload: EmployeeUpdate, db: AsyncIOMotorDatabase = Depends(get_db)
):
    doc = await _get_employee_or_404(employee_id, db)
    oid = doc["_id"]
    if await db.employees.find_one({"employee_id": payload.employee_id, "_id": {"$ne": oid}}):
        raise HTTPException(status_code=400, detail="An employee with this ID already exists.")
    if await db.employees.find_one({"email": payload.email, "_id": {"$ne": oid}}):
        raise HTTPException(status_code=400, detail="An employee with this email already exists.")
    await db.employees.update_one({"_id": oid}, {"$set": payload.model_dump()})
    updated = await db.employees.find_one({"_id": oid})
    return await _build_employee_out(updated, db)


@router.delete("/{employee_id}")
async def delete_employee(employee_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await _get_employee_or_404(employee_id, db)
    oid = doc["_id"]
    # Cascade-delete attendance records for this employee
    await db.attendance.delete_many({"employee_id": oid})
    await db.employees.delete_one({"_id": oid})
    return {"message": "Employee deleted successfully."}
