import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "hrms_fastapi")

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-use-long-random-string")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", 7))

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
