from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import Optional

from ..database import get_db
from ..dependencies import get_current_user, require_roles
from ..schemas.holidays import HolidayCreate, HolidayOut

router = APIRouter(prefix="/holidays", tags=["holidays"])

HR_ROLES = ["super_admin", "hr_admin", "hr_manager"]


@router.get("/", response_model=list[HolidayOut])
async def list_holidays(
    year: Optional[int] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    query = {"year": year or datetime.now(timezone.utc).year}
    docs = await db.holidays.find(query).sort("date", 1).to_list(length=None)
    return [
        HolidayOut(id=str(d["_id"]), **{k: v for k, v in d.items() if k != "_id"})
        for d in docs
    ]


@router.post("/", response_model=HolidayOut, status_code=status.HTTP_201_CREATED)
async def create_holiday(
    payload: HolidayCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ROLES)),
):
    data = payload.model_dump()
    data["date"] = data["date"].isoformat()
    data["created_at"] = datetime.now(timezone.utc)
    result = await db.holidays.insert_one(data)
    doc = await db.holidays.find_one({"_id": result.inserted_id})
    return HolidayOut(id=str(doc["_id"]), **{k: v for k, v in doc.items() if k != "_id"})


@router.delete("/{hol_id}")
async def delete_holiday(
    hol_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(require_roles(HR_ROLES)),
):
    if not ObjectId.is_valid(hol_id):
        raise HTTPException(status_code=404, detail="Holiday not found")
    await db.holidays.delete_one({"_id": ObjectId(hol_id)})
    return {"message": "Holiday deleted"}
