# VEXTRO Local Run and Browser Testing Guide

## Project location

The complete project is saved at:

```text
E:\Vextro
```

Important folders:

- Backend: `E:\Vextro\backend`
- Frontend: `E:\Vextro\frontend`
- Database migrations: `E:\Vextro\backend\migrations`
- Documentation: `E:\Vextro\docs`

## Local demo accounts

These accounts are for local development only:

| Role | Email | Password |
|---|---|---|
| Consumer | `demo.consumer@vextro.com` | `VextroDemo@2026!` |
| SME | `demo.sme@vextro.com` | `VextroDemo@2026!` |
| Admin | `demo.admin@vextro.com` | VextroDemo@2026!`` |

Never use this shared demo password in production.

## Start the application locally

PostgreSQL must already be running and `backend\.env` must contain the correct
database and JWT settings.

### Terminal 1 - Backend

```powershell
cd E:\Vextro\backend
.\.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Backend URLs:

- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/v1/health`
- Database health: `http://127.0.0.1:8000/api/v1/database/health`

### Terminal 2 - Frontend

```powershell
cd E:\Vextro\frontend
npm install
npm run dev
```

Open the website at:

```text
http://localhost:5173
```

Keep both terminals open while testing. Stop either server with `Ctrl+C`.

## Public and role-based views

### Public visitor

- Home page
- Product search and filters
- Product details and marketplace offers
- Cross-platform comparison
- Historical-price chart
- ML price forecast or an honest insufficient-data state
- Generic best-time-to-buy guidance

### Consumer

Everything public, plus:

- Consumer dashboard
- Personalized buy guidance using the saved target price
- Create, update, deactivate and delete price alerts
- In-app notification bell and read/unread state
- Database-grounded shopping assistant

Recommended routes: `/dashboard`, `/products`, `/compare`, `/alerts`,
`/assistant`.

### SME

Everything public, plus:

- SME dashboard/workspace
- Business organization profile
- Business-product and stock management
- Sales CSV import and analytics
- Competitor watchlist and competitor intelligence
- Pricing scenario simulation and reports
- SME notifications

Recommended routes: `/dashboard`, `/sme`, `/products`.

### Admin

Admin can access public, Consumer and SME tools, plus:

- Admin operational dashboard
- User search and activation/deactivation
- Catalog/product/listing management
- Scraper and ingestion monitoring
- Product-match review
- System statistics and health information

Recommended routes: `/dashboard`, `/admin`, `/sme`, `/alerts`, `/assistant`.

## Browser test order

1. Open `http://localhost:5173` without logging in.
2. Test product search, product details, comparison and price history.
3. Login as Consumer and test alerts, assistant and notifications.
4. Logout, login as SME and test the SME workspace.
5. Logout, login as Admin and test user/catalog/operations screens.
6. Open Swagger at `http://127.0.0.1:8000/docs` for direct API testing.

## Recreate the demo accounts

If the demo accounts are deleted or their passwords need resetting:

```powershell
cd E:\Vextro\backend
$env:VEXTRO_DEMO_PASSWORD = "VextroDemo@2026!"
python scripts\seed_demo_users.py
Remove-Item Env:VEXTRO_DEMO_PASSWORD
```

The seeder changes only the dedicated `demo.*@vextro.com` accounts. It does
not reset existing personal accounts.
