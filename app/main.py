from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.core.deps import DbSession
from app.core.errors import AppError, register_exception_handlers
from app.database import Base, SessionLocal, engine
from app.routers import (
    admin,
    auth,
    credit,
    merchant,
    notifications,
    payment_methods,
    plans,
    products,
    store,
    transactions,
)
from app.services.decisioning import ensure_risk_tiers

DESCRIPTION = """
Mini-Affirm, modeled on **affirm.com**. Three kinds of users:

* **Consumers** browse the store, check out with Affirm (soft credit check, instant decision), compare plans,
  accept the loan agreement, then manage loans, autopay, payment methods and payments.
* **Merchants** apply, get approved, configure financing programs (terms, 0% APR promos, order limits),
  and capture or void the orders Affirm approved.
* **Admins** (internal) approve merchants, edit risk tiers, work the manual-review queue, watch delinquency
  and run the daily servicing job.

**How to authenticate:** click **Authorize**, enter an email as `username` plus the password.
Demo accounts (after `python -m app.seed`), all with password `Password123!`: `admin@demo.com`,
`shop@demo.com` / `home@demo.com` (merchants), `newshop@demo.com` (pending merchant),
`alice@demo.com`, `bob@demo.com`, `carol@demo.com`, `dave@demo.com`, `erin@demo.com` (consumers).

Every error has the shape `{"detail": "...", "code": "..."}`. Money values are strings with 2 decimals.
"""

TAGS = [
    {"name": "Auth", "description": "Register, log in (JWT), log out. Not counted as business endpoints."},
    {"name": "Store", "description": "Products from active merchants, with promo messaging."},
    {"name": "Credit", "description": "Soft credit check and spending power."},
    {"name": "Transactions", "description": "Checkout, decision, plan comparison and selection, capture and void."},
    {"name": "Plans", "description": "Installment plans: schedule, autopay, payments."},
    {"name": "Payment methods", "description": "Mock bank accounts and debit cards."},
    {"name": "Notifications", "description": "In-app messages: approvals, payments, reminders."},
    {"name": "Products", "description": "Merchant catalog."},
    {"name": "Merchant", "description": "Financing programs and payout summary."},
    {"name": "Admin", "description": "Internal operators: onboarding, risk, review, delinquency, jobs, audit."},
    {"name": "Health", "description": "Deployment check."},
]

def add_missing_columns(bind: Engine) -> None:
    """Tiny stand-in for a migration tool: create_all makes new tables but never adds columns to
    existing ones, so columns added after a deploy are added here (Postgres only; idempotent)."""
    if bind.dialect.name != "postgresql":
        return
    with bind.begin() as conn:
        conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 1"))


# lifespan is FastAPI's hook for startup and shutdown logic
@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    add_missing_columns(engine)
    with SessionLocal() as db:
        ensure_risk_tiers(db)
        db.commit()
    yield


app = FastAPI(
    title="Mini-Affirm API",
    version="2.0.0",
    description=DESCRIPTION,
    openapi_tags=TAGS,
    lifespan=lifespan,
    root_path=settings.root_path,
)
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True, # lets the browser send cookies and Authorization headers on cross-origin requests
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, store, credit, transactions, plans, payment_methods, notifications, products, merchant,
               admin):
    app.include_router(module.router)


@app.get("/health", tags=["Health"], summary="Health check (API + database)")
def health(db: DbSession) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1")) # asks the database to return the number 1
    except SQLAlchemyError:
        raise AppError(503, "DATABASE_UNAVAILABLE", "Database is not reachable.")
    return {"status": "ok", "database": "ok"}
