from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import Optional

from ..database import get_db
from ..dependencies import get_current_user, require_roles
from ..schemas.departments import DepartmentCreate, DepartmentOut, DesignationCreate, DesignationOut

router = APIRouter(tags=["departments"])

HR_ROLES = ["super_admin", "hr_admin"]


# ── Departments ──────────────────────────────────────────────────────────────

@router.get("/departments/", response_model=list[DepartmentOut])
async def list_departments(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    docs = await db.departments.find({}).sort("name", 1).to_list(length=None)
    result = []
    for d in docs:
        head_name = None
        if d.get("head_id"):
            emp = await db.employees.find_one({"_id": d["head_id"]})
            head_name = emp["full_name"] if emp else None
        count = await db.employees.count_documents({"department_id": d["_id"]})
        result.append(DepartmentOut(
            id=str(d["_id"]),
            name=d["name"],
            head_id=str(d["head_id"]) if d.get("head_id") else None,
            head_name=head_name,
            employee_count=count,
            created_at=d["created_at"],
        ))
    return result


@router.post("/departments/", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ROLES)),
):
    if await db.departments.find_one({"name": {"$regex": f"^{payload.name}$", "$options": "i"}}):
        raise HTTPException(status_code=400, detail="Department already exists")
    data = {"name": payload.name, "head_id": None, "created_at": datetime.now(timezone.utc)}
    if payload.head_id and ObjectId.is_valid(payload.head_id):
        data["head_id"] = ObjectId(payload.head_id)
    result = await db.departments.insert_one(data)
    doc = await db.departments.find_one({"_id": result.inserted_id})
    return DepartmentOut(
        id=str(doc["_id"]),
        name=doc["name"],
        head_id=str(doc["head_id"]) if doc.get("head_id") else None,
        employee_count=0,
        created_at=doc["created_at"],
    )


@router.put("/departments/{dept_id}", response_model=DepartmentOut)
async def update_department(
    dept_id: str,
    payload: DepartmentCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ROLES)),
):
    if not ObjectId.is_valid(dept_id):
        raise HTTPException(status_code=404, detail="Department not found")
    oid = ObjectId(dept_id)
    if not await db.departments.find_one({"_id": oid}):
        raise HTTPException(status_code=404, detail="Department not found")
    update = {"name": payload.name}
    if payload.head_id and ObjectId.is_valid(payload.head_id):
        update["head_id"] = ObjectId(payload.head_id)
    await db.departments.update_one({"_id": oid}, {"$set": update})
    doc = await db.departments.find_one({"_id": oid})
    count = await db.employees.count_documents({"department_id": oid})
    return DepartmentOut(
        id=str(doc["_id"]),
        name=doc["name"],
        head_id=str(doc["head_id"]) if doc.get("head_id") else None,
        employee_count=count,
        created_at=doc["created_at"],
    )


@router.delete("/departments/{dept_id}")
async def delete_department(
    dept_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ROLES)),
):
    if not ObjectId.is_valid(dept_id):
        raise HTTPException(status_code=404, detail="Department not found")
    oid = ObjectId(dept_id)
    if await db.employees.count_documents({"department_id": oid}) > 0:
        raise HTTPException(status_code=400, detail="Cannot delete a department that has employees")
    await db.departments.delete_one({"_id": oid})
    return {"message": "Department deleted successfully"}


# ── Designations ─────────────────────────────────────────────────────────────

@router.get("/designations/", response_model=list[DesignationOut])
async def list_designations(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    docs = await db.designations.find({}).sort("title", 1).to_list(length=None)
    result = []
    for d in docs:
        dept_name = None
        if d.get("department_id"):
            dept = await db.departments.find_one({"_id": d["department_id"]})
            dept_name = dept["name"] if dept else None
        result.append(DesignationOut(
            id=str(d["_id"]),
            title=d["title"],
            department_id=str(d["department_id"]) if d.get("department_id") else None,
            department_name=dept_name,
            salary_grade=d.get("salary_grade"),
            created_at=d["created_at"],
        ))
    return result


@router.post("/designations/", response_model=DesignationOut, status_code=status.HTTP_201_CREATED)
async def create_designation(
    payload: DesignationCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ROLES)),
):
    data = {"title": payload.title, "salary_grade": payload.salary_grade, "department_id": None, "created_at": datetime.now(timezone.utc)}
    if payload.department_id and ObjectId.is_valid(payload.department_id):
        data["department_id"] = ObjectId(payload.department_id)
    result = await db.designations.insert_one(data)
    doc = await db.designations.find_one({"_id": result.inserted_id})
    return DesignationOut(
        id=str(doc["_id"]),
        title=doc["title"],
        department_id=str(doc["department_id"]) if doc.get("department_id") else None,
        salary_grade=doc.get("salary_grade"),
        created_at=doc["created_at"],
    )


@router.delete("/designations/{desig_id}")
async def delete_designation(
    desig_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ROLES)),
):
    if not ObjectId.is_valid(desig_id):
        raise HTTPException(status_code=404, detail="Designation not found")
    await db.designations.delete_one({"_id": ObjectId(desig_id)})
    return {"message": "Designation deleted successfully"}
