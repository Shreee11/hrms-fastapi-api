import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .database import connect_db, close_db
from .routers import employees, attendance, auth, departments, leave, payroll, reports, onboarding, documents, holidays

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="HRMS API",
    description="Human Resource Management System REST API built with FastAPI and MongoDB",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
cors_origins = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

cors_origin_regex = os.environ.get(
    "CORS_ORIGIN_REGEX", r"https://hrms-lite.*\.vercel\.app"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api")
app.include_router(employees.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")
app.include_router(departments.router, prefix="/api")
app.include_router(leave.router, prefix="/api")
app.include_router(payroll.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(holidays.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "HRMS API v2.0 is running"}
