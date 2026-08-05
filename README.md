# VEXTRO

VEXTRO is an AI-powered e-commerce intelligence platform for comparing product listings across **Daraz** and **PriceOye**. It provides product search, price comparison, historical price charts, price alerts, consumer tools, and administrator monitoring.

## Current Status

Working modules:

- React frontend connected with FastAPI
- PostgreSQL database with Alembic migrations
- JWT authentication and role-based access
- Consumer, SME, and Admin roles
- Product catalog, search, filters, and pagination
- Product details and Daraz/PriceOye listing comparison
- Price history and price alerts
- Consumer dashboard
- Admin dashboard
- Admin user, product, and marketplace-listing management
- Backend API tests and frontend production build

Next development phase:

- Daraz and PriceOye data acquisition
- Data normalization and product matching
- AI forecasting, sentiment, recommendations, and SME intelligence

## Technology Stack

- **Frontend:** React, Vite, Tailwind CSS, Axios, React Router, Recharts
- **Backend:** FastAPI, Python
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy
- **Migrations:** Alembic
- **Testing:** Pytest and FastAPI TestClient
- **Version Control:** Git and GitHub

## Project Structure

```text
vextro/
├── backend/
│   ├── app/
│   ├── migrations/
│   ├── tests/
│   ├── requirements.txt
│   └── alembic.ini
├── frontend/
│   ├── src/
│   ├── package.json
│   └── package-lock.json
├── docs/
├── scraper/
├── ml/
└── README.md
```

# Run the Project on a New PC

## 1. Install Requirements

Install:

- Git
- Python 3.11 or 3.12
- Node.js LTS
- PostgreSQL
- pgAdmin

Verify:

```powershell
git --version
python --version
node --version
npm --version
psql --version
```

## 2. Clone the Repository

```powershell
git clone https://github.com/abdulmunim18/vextro.git
cd vextro
```

## 3. Create the PostgreSQL Database

Open pgAdmin Query Tool and run:

```sql
CREATE ROLE vextro_app
WITH LOGIN
PASSWORD 'your_local_password';

CREATE DATABASE vextro_db
OWNER vextro_app;
```

## 4. Backend Setup

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

When PowerShell blocks virtual-environment activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

For macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 5. Backend Environment File

Copy the example file:

```powershell
Copy-Item .env.example .env
```

Open `backend/.env` and update the local values.

Main settings:

```env
DATABASE_URL=postgresql+psycopg://vextro_app:your_local_password@localhost:5432/vextro_db
JWT_SECRET=replace_with_a_long_random_secret
FRONTEND_ORIGIN=http://localhost:5173
```

Generate a JWT secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Never commit `.env`.

## 6. Apply Database Migrations

Run inside the `backend` folder:

```powershell
alembic upgrade head
```

Verify:

```powershell
alembic current
```

## 7. Run Backend Tests

```powershell
python -m pytest -q
```

## 8. Start the Backend

```powershell
uvicorn app.main:app --reload
```

Backend URLs:

- Health: `http://127.0.0.1:8000/health`
- Database health: `http://127.0.0.1:8000/database/health`
- Swagger: `http://127.0.0.1:8000/docs`

Keep the backend terminal running.

## 9. Frontend Setup

Open a second terminal:

```powershell
cd path\to\vextro\frontend
npm install
npm run build
npm run dev
```

Open:

```text
http://localhost:5173
```

When the frontend branch uses an environment variable, create `frontend/.env.local`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Never commit `.env.local`.

# Daily Startup

Backend terminal:

```powershell
cd path\to\vextro\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Frontend terminal:

```powershell
cd path\to\vextro\frontend
npm run dev
```

# Fresh Database Note

Alembic migrations create the schema and repository-controlled reference data.

When the product catalog is empty on a new PC, import the latest team-approved demo seed or database dump before testing product comparison and admin listings.

Public registration supports Consumer and SME accounts. Administrator access should be created through the approved project seed/setup process, not public registration.

# Development Checks

Backend:

```powershell
cd backend
python -m pytest -q
```

Frontend:

```powershell
cd frontend
npm run build
```

Git:

```powershell
git status --short
git diff --check
```

# Team Workflow

Do not push unfinished work directly to `main`.

```text
feature branch
    ↓
tests and build
    ↓
commit
    ↓
push
    ↓
pull request
    ↓
review
    ↓
merge into main
```

Example:

```powershell
git switch -c feature/module-name
git add .
git commit -m "Complete module checkpoint"
git push -u origin feature/module-name
```

## Module Ownership

| Member | Responsibility |
|---|---|
| Abdul Munim | Full-stack integration, consumer support, BI, chatbot, pricing advisor |
| Member 2 | Data acquisition, normalization, warehouse operations, trust verification |
| Member 3 | Price forecasting, sentiment analysis, recommendations, demand forecasting |

# Common Problems

### Backend cannot connect to PostgreSQL

Check the database name, username, password, port `5432`, and `DATABASE_URL` in `backend/.env`.

### Alembic configuration error

Run Alembic from the `backend` folder where `alembic.ini` exists.

### Frontend cannot connect to backend

Confirm that:

- Backend is running on port `8000`
- Frontend is running on port `5173`
- `FRONTEND_ORIGIN` is correct
- The API base URL ends with `/api/v1`

### Port already in use

Backend alternative:

```powershell
uvicorn app.main:app --reload --port 8001
```

Update the frontend API URL when changing the backend port.

---

**VEXTRO — Smarter Shopping. Better Decisions.**
