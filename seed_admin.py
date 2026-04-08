"""
Seed script — creates one test user for each role in MongoDB.

Usage:
    cd fastapi-backend
    python seed_admin.py

Test credentials (all passwords: Test@123):
    super_admin   →  superadmin@hrms.com
    hr_admin      →  hradmin@hrms.com
    hr_manager    →  hrmanager@hrms.com
    team_manager  →  teammanager@hrms.com
    employee      →  employee@hrms.com

Change passwords immediately in production!
"""
import asyncio
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from motor.motor_asyncio import AsyncIOMotorClient
import app.config as config
from app.utils.password import hash_password


PASSWORD = "Test@123"

TEST_USERS = [
    {"email": "superadmin@hrms.com",  "full_name": "Super Admin",   "role": "super_admin"},
    {"email": "hradmin@hrms.com",     "full_name": "HR Admin",       "role": "hr_admin"},
    {"email": "hrmanager@hrms.com",   "full_name": "HR Manager",     "role": "hr_manager"},
    {"email": "teammanager@hrms.com", "full_name": "Team Manager",   "role": "team_manager"},
    {"email": "employee@hrms.com",    "full_name": "Test Employee",  "role": "employee"},
]


async def seed():
    client = AsyncIOMotorClient(config.MONGODB_URL)
    db = client[config.DATABASE_NAME]

    for user in TEST_USERS:
        existing = await db.users.find_one({"email": user["email"]})
        if existing:
            print(f"[skip] Already exists: {user['email']} ({user['role']})")
            continue

        await db.users.insert_one({
            "email": user["email"],
            "password_hash": hash_password(PASSWORD),
            "role": user["role"],
            "full_name": user["full_name"],
            "is_active": True,
            "failed_attempts": 0,
            "locked_until": None,
            "refresh_token": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
        print(f"[ok]   Created: {user['email']}  role={user['role']}")

    print()
    print("All users use password: Test@123")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
