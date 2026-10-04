"""Demo data. Run with `python -m app.seed` (or `docker compose exec api python -m app.seed`).

Idempotent: does nothing if any user already exists. Plans and payments are created through the
real services, so every number matches the business logic.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import Product, Transaction, TransactionStatus, User, UserRole, utcnow
from app.services.payments import apply_payment
from app.services.plans import ensure_plan_offers, select_plan

DEMO_PASSWORD = "Password123!"


def seed(db: Session) -> bool:
    ensure_plan_offers(db)
    if db.scalar(select(User.id).limit(1)) is not None:
        db.commit()
        return False

    hashed = hash_password(DEMO_PASSWORD)
    now = utcnow()
    shop = User(email="shop@demo.com", hashed_password=hashed, role=UserRole.merchant, created_at=now)
    alice = User(email="alice@demo.com", hashed_password=hashed, role=UserRole.consumer, created_at=now)
    bob = User(email="bob@demo.com", hashed_password=hashed, role=UserRole.consumer, created_at=now)
    db.add_all([shop, alice, bob])
    db.flush()

    headphones = Product(merchant_id=shop.id, name="Headphones", price=Decimal("120.00"), created_at=now)
    laptop = Product(merchant_id=shop.id, name="Laptop", price=Decimal("1000.00"), created_at=now)
    sofa = Product(merchant_id=shop.id, name="Sofa", price=Decimal("2400.00"), created_at=now)
    db.add_all([headphones, laptop, sofa])
    db.flush()

    def purchase(consumer: User, product: Product) -> Transaction:
        tx = Transaction(
            consumer_id=consumer.id,
            merchant_id=shop.id,
            product=product,
            amount=product.price,
            status=TransactionStatus.pending_plan,
            created_at=utcnow(),
        )
        db.add(tx)
        db.flush()
        return tx

    # Alice: one purchase still waiting for a plan choice.
    purchase(alice, headphones)

    # Alice: an active 12-month plan with the first two installments paid.
    active = select_plan(db, purchase(alice, sofa), term_months=12, autopay_day=15)
    apply_payment(active, active.installments[0].amount_due + active.installments[1].amount_due)

    # Alice: a 3-month 0% plan that is fully paid off.
    paid_off = select_plan(db, purchase(alice, laptop), term_months=3, autopay_day=1)
    apply_payment(paid_off, paid_off.remaining_balance)

    # Bob: a pending purchase, so his list differs from Alice's.
    purchase(bob, headphones)

    db.commit()
    return True


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        created = seed(db)
    if created:
        print(f"Seeded demo data. Accounts (password {DEMO_PASSWORD}):")
        print("  merchant: shop@demo.com\n  consumers: alice@demo.com, bob@demo.com")
    else:
        print("Users already exist; skipped demo data (plan offers ensured).")


if __name__ == "__main__":
    main()
