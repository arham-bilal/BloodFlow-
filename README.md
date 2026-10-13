# BloodLink
Matching/communication platform only. Not a replacement for medical professionals or blood-bank procedures.

## Local setup
1. PostgreSQL: `createdb bloodlink` (user/password of your choice).
2. `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
3. `cp .env.example .env` and fill DATABASE_URL, JWT_SECRET (`openssl rand -hex 32`), RESEND_API_KEY, EMAIL_FROM, GOOGLE_MAPS_API_KEY.
4. Set `CREATE_TABLES=true` in `backend/.env` when you want local development to create missing tables, then run `uvicorn main:app --reload` (API docs: http://localhost:8000/docs).
5. Admin: `python create_admin.py`, then login at /login.html; Admin link appears in nav. Demo seeding does not create administrator accounts.
6. Frontend: `cd frontend && python -m http.server 5500` -> http://localhost:5500
7. Tests: `PYTHONPATH=. pytest`

## Services
- Resend: verify a domain, create API key; `EMAIL_FROM` must use the verified domain.
- Google Maps: enable Maps JavaScript + Places, restrict key by HTTP referrer.

## Production
Migrations: `alembic init migrations`, set target_metadata=Base.metadata, `alembic revision --autogenerate -m init && alembic upgrade head`; leave `CREATE_TABLES` unset/false in production and apply migrations separately.
Run `gunicorn -k uvicorn.workers.UvicornWorker main:app` behind HTTPS; set CORS_ORIGINS and `window.API_BASE` in each HTML page before app.js.
Set `API_DOCS_ENABLED=false` in production to disable `/docs`, `/redoc`, and `/openapi.json`.
