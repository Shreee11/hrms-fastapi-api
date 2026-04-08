from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class HolidayCreate(BaseModel):
    name: str
    date: date
    year: int
    holiday_type: str = "general"   # general | restricted


class HolidayOut(HolidayCreate):
    id: str
    created_at: datetime
