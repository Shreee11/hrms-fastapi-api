from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class DocumentCreate(BaseModel):
    employee_id: str
    doc_type: str   # offer_letter | contract | id_proof | certificate | other
    title: str
    file_name: str
    file_type: str  # mime type e.g. application/pdf
    file_data: str  # base64-encoded file contents
    notes: Optional[str] = None


class DocumentOut(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    doc_type: str
    title: str
    file_name: str
    file_type: str
    notes: Optional[str]
    uploaded_by: str
    created_at: datetime
