from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.core.deps import DbSession
from app.core.errors import AppError, register_exception_handlers
from app.database import Base, SessionLocal, engine
from app.routers import auth, plans, products, transactions
from app.services.plans import ensure_plan_offers

DESCRIPTION = """
Backend MVP modeled on **affirm.com**: consumers compare transparent installment plans for a purchase,
select one, view the amortization schedule, change the autopay day and pay it down.

**How to authenticate:** click **Authorize**, enter an email as `username` plus the password.
Demo accounts (after `python -m app.seed`): `shop@demo.com` (merchant), `alice@demo.com`, `bob@demo.com`
(consumers), all with password `Password123!`.

Every error has the shape `{"detail": "...", "code": "..."}`. Money values are strings with 2 decimals.
"""

TAGS = [
    {"name": "Auth", "description": "Register, log in (JWT), log out. Not counted as business endpoints."},
    {"name": "Products", "description": "Merchant catalog."},
    {"name": "Transactions", "description": "Purchases (checkouts), plan comparison and plan selection."},
    {"name": "Plans", "description": "Installment plans: schedule, autopay day, payments."},
    {"name": "Health", "description": "Deployment check."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        ensure_plan_offers(db)
        db.commit()
    yield


app = FastAPI(
    title="Affirm-style Installment Plan API",
    version="1.0.0",
    description=DESCRIPTION,
    openapi_tags=TAGS,
    lifespan=lifespan,
)
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, products, transactions, plans):
    app.include_router(module.router)


@app.get("/health", tags=["Health"], summary="Health check (API + database)")
def health(db: DbSession) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise AppError(503, "DATABASE_UNAVAILABLE", "Database is not reachable.")
    return {"status": "ok", "database": "ok"}
