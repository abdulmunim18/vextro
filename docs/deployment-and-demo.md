# VEXTRO Deployment and Demo Reliability

## Docker startup

1. Copy `.env.docker.example` to `.env.docker` and replace every secret.
2. Build and start the stack:

   ```powershell
   docker compose --env-file .env.docker up --build -d
   ```

3. Open `http://localhost:8080` and verify:

   ```powershell
   Invoke-RestMethod http://localhost:8080/api/v1/health
   Invoke-RestMethod http://localhost:8080/api/v1/database/health
   ```

The backend container applies Alembic migrations before starting. PostgreSQL data is stored in the named `vextro_postgres_data` volume.

## Safe shutdown and backup

Stop services without deleting database data:

```powershell
docker compose --env-file .env.docker down
```

Create a logical backup:

```powershell
docker compose --env-file .env.docker exec -T db pg_dump -U vextro_app -d vextro_db > vextro-backup.sql
```

Do not use `down -v` unless the named database volume is intentionally being deleted and a verified backup exists.

## Demo fallback modes

- Marketplace unavailable: use saved fixtures and seeded catalog data.
- Internet unavailable: run the Docker stack locally.
- AI dependency unavailable: the assistant returns deterministic database-grounded catalog, comparison, price-history and rule-based buy/wait responses.
- Limited price history: the UI shows low confidence and observation coverage instead of claiming a reliable forecast.
- Deployment unavailable: use local backend and frontend startup documented in the root README.

## Final demo sequence

1. Search and filter products by platform, price, rating and availability.
2. Compare two products and show normalized specifications and offers.
3. Open buy/wait guidance and explain confidence/data coverage.
4. Create a price alert and demonstrate an in-app notification.
5. Ask the assistant for a grounded comparison and follow-up price history.
6. Open the SME workspace, competitor risk metrics and PDF/Excel exports.
7. Run dynamic pricing scenarios and explain that they are advisory only.
