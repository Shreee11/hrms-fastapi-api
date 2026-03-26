# HRMS Lite — FastAPI Backend

A REST API for the HRMS Lite application built with **FastAPI**, **Motor**, and **MongoDB**.

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115 |
| DB Driver | Motor 3.7 (async MongoDB driver) |
| Database | MongoDB 6+ |
| Validation | Pydantic v2 |
| Server | Uvicorn |

## Project Structure

```
fastapi-backend/
├── app/
│   ├── main.py          # FastAPI app, CORS, lifespan (connect/close DB)
│   ├── database.py      # Motor client, get_db() dependency, index setup
│   ├── models.py        # serialize_doc() helper (ObjectId → str)
│   ├── schemas.py       # Pydantic request/response schemas
│   └── routers/
│       ├── employees.py # Employee CRUD + dashboard endpoint
│       └── attendance.py# Attendance CRUD + filtering
├── requirements.txt
├── .env.example
└── README.md
```

## Local Setup

### Prerequisites

- Python 3.10+
- MongoDB 6+ running locally ([install guide](https://www.mongodb.com/docs/manual/installation/))

### 1. Start MongoDB

```powershell
# Windows — start as a service (if installed)
net start MongoDB

# Or run manually
mongod --dbpath "C:\data\db"
```

> No database or collection creation needed — MongoDB creates them automatically on first write.

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure environment variables

```powershell
copy .env.example .env
```

Edit `.env`:

```env
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=hrms_fastapi
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

For **MongoDB Atlas** (cloud), replace `MONGODB_URL` with your connection string:

```env
MONGODB_URL=mongodb+srv://<user>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority
```

### 5. Run the development server

```powershell
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

> Collections (`employees`, `attendance`) and their indexes are created automatically on first startup.

---

## MongoDB Data Structure

### employees collection

```json
{
  "_id": ObjectId("..."),
  "employee_id": "EMP001",
  "full_name": "John Doe",
  "email": "john@example.com",
  "department": "Engineering",
  "created_at": ISODate("2026-03-26T10:00:00Z")
}
```

### attendance collection

```json
{
  "_id": ObjectId("..."),
  "employee_id": ObjectId("..."),
  "date": "2026-03-26",
  "status": "Present",
  "created_at": ISODate("2026-03-26T10:00:00Z")
}
```

**Indexes created on startup:**
- `employees.employee_id` — unique
- `employees.email` — unique
- `attendance.(employee_id, date)` — unique compound

---

## API Endpoints

> All IDs in request/response are MongoDB ObjectId strings (24-character hex, e.g. `"6603a1f2e4b0a1c2d3e4f5a6"`).

### Employees — `/api/employees/`

| Method | Path | Description |
|---|---|---|
| GET | `/api/employees/` | List all employees (optional `?search=`) |
| POST | `/api/employees/` | Create employee |
| GET | `/api/employees/dashboard` | Dashboard summary |
| GET | `/api/employees/{id}` | Get employee by ObjectId |
| PUT | `/api/employees/{id}` | Update employee |
| DELETE | `/api/employees/{id}` | Delete employee + their attendance |

### Attendance — `/api/attendance/`

| Method | Path | Description |
|---|---|---|
| GET | `/api/attendance/` | List records (filters: `?employee=<ObjectId>`, `?date=`, `?date_from=`, `?date_to=`) |
| POST | `/api/attendance/` | Mark attendance |
| GET | `/api/attendance/{id}` | Get record by ObjectId |
| PUT | `/api/attendance/{id}` | Update record |
| DELETE | `/api/attendance/{id}` | Delete record |

### Dashboard response shape

```json
{
  "total_employees": 12,
  "total_departments": 3,
  "department_counts": [
    {"department": "Engineering", "count": 5},
    {"department": "HR", "count": 4}
  ]
}
```

---

## Deploying on Render

### Prerequisites

- A [Render](https://render.com) account
- A [MongoDB Atlas](https://www.mongodb.com/atlas) cluster (free M0 tier works)

---

### Step 1 — Set up MongoDB Atlas

1. Go to [MongoDB Atlas](https://www.mongodb.com/atlas) and create a free **M0** cluster.
2. Under **Database Access**, create a database user with a username and password.
3. Under **Network Access**, click **Add IP Address → Allow Access from Anywhere** (`0.0.0.0/0`).
4. Click **Connect → Drivers** and copy the connection string. It looks like:
   ```
   mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```

---

### Step 2 — Add a `render.yaml` to this folder

Create `fastapi-backend/render.yaml`:

```yaml
services:
  - type: web
    name: hrms-fastapi-api
    runtime: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn -k uvicorn.workers.UvicornWorker app.main:app"
    envVars:
      - key: MONGODB_URL
        sync: false          # set manually in Render dashboard (keeps secret safe)
      - key: DATABASE_NAME
        value: hrms_fastapi
      - key: CORS_ALLOWED_ORIGINS
        value: https://hrms-lite.vercel.app
```

---

### Step 3 — Push to GitHub

Make sure your `fastapi-backend/` folder is pushed to its own GitHub repo (e.g. `hrms-fastapi-api`).

---

### Step 4 — Create a Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com) → **New → Web Service**.
2. Connect your GitHub repo (`hrms-fastapi-api`).
3. Set the following:
   | Field | Value |
   |---|---|
   | **Root Directory** | *(leave blank — repo root is `fastapi-backend/`)* |
   | **Runtime** | Python |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `gunicorn -k uvicorn.workers.UvicornWorker app.main:app` |

---

### Step 5 — Set Environment Variables

In the Render service → **Environment** tab, add:

| Key | Value |
|---|---|
| `MONGODB_URL` | Your Atlas connection string |
| `DATABASE_NAME` | `hrms_fastapi` |
| `CORS_ALLOWED_ORIGINS` | `https://hrms-lite.vercel.app` |

---


### Step 6 — Deploy

Click **Deploy**. Render will install dependencies, start Uvicorn via Gunicorn, and your API will be live at:

```
https://hrms-fastapi-api.onrender.com
```

Swagger docs will be available at:

```
https://hrms-fastapi-api.onrender.com/docs
```

> **Note:** On Render's free tier the service spins down after 15 minutes of inactivity. The first request after sleep will take ~30 seconds to wake up.

