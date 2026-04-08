from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from ..database import get_db
from ..utils.password import hash_password, verify_password
from ..utils.jwt import create_access_token, create_refresh_token, decode_token
from ..dependencies import get_current_user
from ..schemas.auth import LoginRequest, ChangePasswordRequest, RefreshRequest

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "role": user["role"],
        "full_name": user.get("full_name", ""),
        "department": user.get("department", ""),
    }


@router.post("/login")
async def login(payload: LoginRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await db.users.find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    # Reset failed attempts on success
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"failed_attempts": 0, "last_login": datetime.now(timezone.utc)}},
    )

    token_data = {"sub": str(user["_id"]), "role": user["role"]}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store hashed refresh token
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"refresh_token": refresh_token}},
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": _user_out(user),
    }


@router.post("/refresh")
async def refresh_token(payload: RefreshRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    data = decode_token(payload.refresh_token)
    if not data or data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = data.get("sub")
    if not user_id or not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user or user.get("refresh_token") != payload.refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    token_data = {"sub": str(user["_id"]), "role": user["role"]}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    await db.users.update_one({"_id": user["_id"]}, {"$set": {"refresh_token": new_refresh}})

    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    await db.users.update_one({"_id": current_user["_id"]}, {"$set": {"refresh_token": None}})
    return {"message": "Logged out successfully"}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return _user_out(current_user)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    new_hash = hash_password(payload.new_password)
    await db.users.update_one({"_id": current_user["_id"]}, {"$set": {"password_hash": new_hash}})
    return {"message": "Password changed successfully"}
