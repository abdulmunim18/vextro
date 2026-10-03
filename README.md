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
- Advanced catalog filters and side-by-side product comparison
- Best-time-to-buy guidance with confidence, data coverage, and authenticated target-price personalization
- Versioned ML price-forecast ingestion, persistence, evaluation metrics, and historical-vs-predicted product chart
- In-app consumer price-drop and SME competitor-risk notifications
- SME competitor price-gap intelligence and PDF/Excel reports
- SME dynamic pricing scenario advisor
- Persistent, database-grounded shopping assistant
- Docker Compose deployment for PostgreSQL, FastAPI and React/Nginx

Team-dependent modules still in development:

- Daraz and PriceOye data acquisition
- Data normalization and product matching
- AI forecasting, sentiment, recommendation-model training, demand forecasting and trust verification

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
│   └── notification-and-reporting-engine.md
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
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=vextro_db
DB_USER=vextro_app
DB_PASSWORD=your_local_password
JWT_SECRET_KEY=replace_with_a_long_random_secret
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Generate a JWT secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Never commit `.env`.

### Notifications (optional, module 6.14)

Email and browser-push notifications stay switched off until you configure
them. Without configuration, in-app notifications keep working and the
other channels are recorded as `skipped`.

```env
FRONTEND_BASE_URL=http://localhost:5173

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=true

VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=

DIGEST_SCHEDULER_ENABLED=false
```

Generate a VAPID key pair (printed to the terminal, never written to disk):

```powershell
python -m scripts.generate_vapid_keys
```

Never commit `VAPID_PRIVATE_KEY` or `SMTP_PASSWORD`. For SMTP and push
setup, digest scheduling and the delivery architecture, see
`docs/notification-and-reporting-engine.md`.

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

Scraper scheduler terminal (crawls once immediately, then every 12 hours):

```powershell
cd path\to\vextro\vextro_scraper
$env:INGESTION_API_KEY = "<same value as backend\.env>"
..\backend\.venv\Scripts\python.exe -m vextro_scraper.scheduler
```

Only one scheduler can run at a time; a second copy exits on its own file
lock. To have the backend start it for you instead, set
`SCRAPER_AUTOSTART_WITH_API=true` in `backend\.env`. See
`docs/smartphone-price-sync.md` for the full configuration, the optional
Windows startup task, and how marketplace prices, history and reviews flow
through the system.

# Docker Startup

From the repository root:

```powershell
Copy-Item .env.docker.example .env.docker
# Replace every secret in .env.docker.
docker compose --env-file .env.docker up --build -d
```

Open `http://localhost:8080`. See `docs/deployment-and-demo.md` for health checks, backup and demo fallbacks.

# Fresh Database Note

Alembic migrations create the schema and repository-controlled reference data.

When the product catalog is empty on a new PC, import the latest team-approved demo seed or database dump before testing product comparison and admin listings.

Public registration supports Consumer and SME accounts. Administrator access should be created through the approved project seed/setup process, not public registration.

## Restoring from a team `pg_dump` (important)

Team dumps in `backups/` (and the ones shared out-of-band) are in `pg_dump` **custom** format, not plain SQL. Use `pg_restore`, not `psql -f`, and always re-run migrations afterward — the dump reflects the schema at the moment it was taken, and any migrations added since then will be missing until you re-apply them. Skipping this step causes the acquisition endpoints to return `500 UndefinedTable` on every scraped item.

Create the databases as `vextro_app` (not `postgres`) so every restored table lands with the correct owner. `REASSIGN OWNED BY postgres TO vextro_app` is not enough on its own because a superuser also owns system catalog rows that cannot be reassigned, and the whole statement aborts before it touches your tables.

```powershell
# 1. Let vextro_app create databases just for this operation.
psql -h 127.0.0.1 -U postgres -d postgres -c "ALTER ROLE vextro_app CREATEDB;"

# 2. Drop and recreate the target DBs as vextro_app so it owns them from the start.
psql -h 127.0.0.1 -U postgres    -d postgres -c "DROP DATABASE IF EXISTS vextro_db WITH (FORCE);"
psql -h 127.0.0.1 -U postgres    -d postgres -c "DROP DATABASE IF EXISTS vextro_test_db WITH (FORCE);"
psql -h 127.0.0.1 -U vextro_app  -d postgres -c "CREATE DATABASE vextro_db;"
psql -h 127.0.0.1 -U vextro_app  -d postgres -c "CREATE DATABASE vextro_test_db;"

# 3. Restore each dump AS vextro_app, dropping the dump's baked-in ownership/privilege grants.
pg_restore -h 127.0.0.1 -U vextro_app -d vextro_db      --no-owner --no-privileges "path\to\vextro_db.sql"
pg_restore -h 127.0.0.1 -U vextro_app -d vextro_test_db --no-owner --no-privileges "path\to\vextro_test_db.sql"

# 4. Apply any migrations added since the dump was taken.
cd backend
alembic upgrade heads

# 5. Revoke the temporary CREATEDB privilege.
psql -h 127.0.0.1 -U postgres -d postgres -c "ALTER ROLE vextro_app NOCREATEDB;"
```

Set `PGPASSWORD` for whichever role you invoke, or supply the password interactively. After step 4, `alembic current` should print the same revision as `alembic heads`, and `curl http://127.0.0.1:8000/database/health` should report `"connected_user":"vextro_app"`.

# Development Checks

Backend:

```powershell
cd backend
python -m pytest -q
```

Scraper:

```powershell
cd vextro_scraper
..\backend\.venv\Scripts\python.exe -m pytest -q
```

Frontend:

```powershell
cd frontend
npm run build
npm run lint
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
