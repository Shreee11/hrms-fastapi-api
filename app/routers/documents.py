import base64
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import List, Optional

from ..database import get_db
from ..dependencies import get_current_user, require_roles
from ..schemas.documents import DocumentCreate, DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])

HR_ROLES = ["super_admin", "hr_admin", "hr_manager"]

DOC_TYPES = ["offer_letter", "contract", "id_proof", "certificate", "payslip", "other"]


async def _build_out(doc: dict, emp: Optional[dict]) -> DocumentOut:
    return DocumentOut(
        id=str(doc["_id"]),
        employee_id=str(doc["employee_id"]),
        employee_name=emp.get("full_name", "") if emp else "",
        doc_type=doc["doc_type"],
        title=doc["title"],
        file_name=doc.get("file_name", ""),
        file_type=doc.get("file_type", ""),
        notes=doc.get("notes"),
        uploaded_by=doc.get("uploaded_by", ""),
        created_at=doc["created_at"],
    )


@router.get("/", response_model=List[DocumentOut])
async def list_documents(
    employee_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    role = current_user.get("role")
    query = {}

    if role in HR_ROLES:
        if employee_id and ObjectId.is_valid(employee_id):
            query["employee_id"] = ObjectId(employee_id)
    else:
        # Non-HR sees only their own documents
        emp = await db.employees.find_one({"email": current_user["email"]})
        if not emp:
            return []
        query["employee_id"] = emp["_id"]

    docs = await db.documents.find(query).sort("created_at", -1).to_list(length=None)
    result = []
    for doc in docs:
        emp = await db.employees.find_one({"_id": doc["employee_id"]})
        result.append(await _build_out(doc, emp))
    return result


@router.post("/", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    payload: DocumentCreate,
    current_user: dict = Depends(require_roles(HR_ROLES)),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if not ObjectId.is_valid(payload.employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    eid = ObjectId(payload.employee_id)
    emp = await db.employees.find_one({"_id": eid})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Validate base64 and approximate size check (16MB MongoDB doc limit)
    try:
        raw = base64.b64decode(payload.file_data)
        if len(raw) > 8 * 1024 * 1024:  # 8MB cap
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 8 MB.")
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail="Invalid file data")

    doc = {
        "employee_id": eid,
        "doc_type": payload.doc_type,
        "title": payload.title,
        "file_name": payload.file_name,
        "file_type": payload.file_type,
        "file_data": payload.file_data,
        "notes": payload.notes,
        "uploaded_by": current_user.get("email", ""),
        "created_at": datetime.now(timezone.utc),
    }
    res = await db.documents.insert_one(doc)
    doc["_id"] = res.inserted_id
    return await _build_out(doc, emp)


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if not ObjectId.is_valid(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    doc = await db.documents.find_one({"_id": ObjectId(doc_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    role = current_user.get("role")
    if role not in HR_ROLES:
        emp = await db.employees.find_one({"email": current_user["email"]})
        if not emp or emp["_id"] != doc["employee_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

    try:
        file_bytes = base64.b64decode(doc["file_data"])
    except Exception:
        raise HTTPException(status_code=500, detail="Corrupt file data")

    return Response(
        content=file_bytes,
        media_type=doc.get("file_type", "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{doc.get("file_name", "document")}"'
        },
    )


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str,
    current_user: dict = Depends(require_roles(HR_ROLES)),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if not ObjectId.is_valid(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    result = await db.documents.delete_one({"_id": ObjectId(doc_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
