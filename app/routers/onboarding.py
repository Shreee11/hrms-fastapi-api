from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import List

from ..database import get_db
from ..dependencies import get_current_user, require_roles
from ..schemas.onboarding import (
    OnboardingStepUpdate, OnboardingOut, OnboardingStep, DEFAULT_STEPS
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

HR_ROLES = ["super_admin", "hr_admin", "hr_manager"]


async def _build_out(rec: dict, emp: dict) -> OnboardingOut:
    steps = [OnboardingStep(**s) for s in rec.get("steps", [])]
    completed_count = sum(1 for s in steps if s.completed)
    progress = int(completed_count / len(steps) * 100) if steps else 0
    return OnboardingOut(
        id=str(rec["_id"]),
        employee_id=str(rec["employee_id"]),
        employee_name=emp.get("full_name", ""),
        employee_eid=emp.get("employee_id", ""),
        department=emp.get("department", ""),
        steps=steps,
        progress=progress,
        created_at=rec["created_at"],
        updated_at=rec["updated_at"],
    )


@router.get("/", response_model=List[OnboardingOut])
async def list_onboarding(
    current_user: dict = Depends(require_roles(HR_ROLES)),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    records = await db.onboarding.find({}).sort("created_at", -1).to_list(length=None)
    result = []
    for rec in records:
        emp = await db.employees.find_one({"_id": rec["employee_id"]})
        if emp:
            result.append(await _build_out(rec, emp))
    return result


@router.post("/{employee_id}", response_model=OnboardingOut, status_code=status.HTTP_201_CREATED)
async def create_onboarding(
    employee_id: str,
    current_user: dict = Depends(require_roles(HR_ROLES)),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if not ObjectId.is_valid(employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    eid = ObjectId(employee_id)
    emp = await db.employees.find_one({"_id": eid})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if await db.onboarding.find_one({"employee_id": eid}):
        raise HTTPException(status_code=400, detail="Onboarding record already exists for this employee")

    now = datetime.now(timezone.utc)
    steps = [
        {"key": s["key"], "label": s["label"], "completed": False,
         "completed_at": None, "notes": None}
        for s in DEFAULT_STEPS
    ]
    rec = {
        "employee_id": eid,
        "steps": steps,
        "created_by": current_user.get("email", ""),
        "created_at": now,
        "updated_at": now,
    }
    res = await db.onboarding.insert_one(rec)
    rec["_id"] = res.inserted_id
    return await _build_out(rec, emp)


@router.patch("/{employee_id}/steps/{step_key}", response_model=OnboardingOut)
async def update_step(
    employee_id: str,
    step_key: str,
    payload: OnboardingStepUpdate,
    current_user: dict = Depends(require_roles(HR_ROLES)),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if not ObjectId.is_valid(employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    eid = ObjectId(employee_id)
    rec = await db.onboarding.find_one({"employee_id": eid})
    if not rec:
        raise HTTPException(status_code=404, detail="Onboarding record not found. Start onboarding first.")
    emp = await db.employees.find_one({"_id": eid})

    now = datetime.now(timezone.utc)
    steps = rec.get("steps", [])
    updated = False
    for step in steps:
        if step["key"] == step_key:
            step["completed"] = payload.completed
            step["completed_at"] = now.isoformat() if payload.completed else None
            step["notes"] = payload.notes
            updated = True
            break
    if not updated:
        raise HTTPException(status_code=404, detail="Step not found")

    await db.onboarding.update_one(
        {"_id": rec["_id"]},
        {"$set": {"steps": steps, "updated_at": now}},
    )
    rec["steps"] = steps
    rec["updated_at"] = now
    return await _build_out(rec, emp)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_onboarding(
    employee_id: str,
    current_user: dict = Depends(require_roles(["super_admin", "hr_admin"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if not ObjectId.is_valid(employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    await db.onboarding.delete_one({"employee_id": ObjectId(employee_id)})
