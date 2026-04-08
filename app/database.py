import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "hrms_fastapi")

_client: Optional[AsyncIOMotorClient] = None


async def connect_db() -> None:
    global _client
    _client = AsyncIOMotorClient(MONGODB_URL)
    db = _client[DATABASE_NAME]

    # Employees
    await db.employees.create_index("employee_id", unique=True)
    await db.employees.create_index("email", unique=True)

    # Attendance
    await db.attendance.create_index(
        [("employee_id", 1), ("date", 1)], unique=True
    )

    # Users
    await db.users.create_index("email", unique=True)

    # Departments
    await db.departments.create_index("name", unique=True)

    # Leave
    await db.leave_requests.create_index([("employee_id", 1), ("created_at", -1)])

    # Payroll
    await db.payroll_runs.create_index([("month", 1), ("year", 1)], unique=True)
    await db.payslips.create_index([("employee_id", 1), ("month", 1), ("year", 1)])

    # Onboarding
    await db.onboarding.create_index("employee_id", unique=True)

    # Documents
    await db.documents.create_index([("employee_id", 1), ("created_at", -1)])


async def close_db() -> None:
    global _client
    if _client:
        _client.close()


def get_db() -> AsyncIOMotorDatabase:
    return _client[DATABASE_NAME]
