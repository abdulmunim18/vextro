# VEXTRO Contributor and Integration Checklist

## Before implementation

- Create a feature branch and keep one subsystem per pull request.
- Define request/response fields before changing an integration boundary.
- Confirm the owning module and any Member 2 or Member 3 dependency.
- Never read model files directly from the frontend; expose a validated backend contract.

## Database changes

- Update the SQLAlchemy model and `backend/app/models/__init__.py`.
- Add one forward and reversible Alembic migration.
- Add ownership/tenant filters for organization data.
- Use transactions and preserve existing seeded demo data.

## API and frontend changes

- Add Pydantic validation, role checks and safe errors.
- Add loading, empty, success and error states.
- Keep the shared VEXTRO navigation, spacing and component styles.
- Do not label heuristic estimates as measured marketplace facts.

## Verification before review

```powershell
cd backend
python -m pytest --collect-only -q
alembic heads
alembic current

cd ..\frontend
npm run lint
npm run build

cd ..
git diff --check
git status --short
```

Run database tests only against the dedicated `TEST_DB_NAME`; the test fixture recreates that database. Include API sample input/output, screenshots and limitations in the pull request.

## Integration review

- Scraper output follows `docs/acquisition-ingestion-contract.md`.
- AI responses include model version, confidence and data coverage.
- Product IDs refer to canonical products and listing IDs to marketplace offers.
- Consumer, SME and Admin authorization is enforced in the backend.
- New routes are included in `app/main.py` and the frontend route tree.
- Migrations have one head and upgrade cleanly from the previous head.
