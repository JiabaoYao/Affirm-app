"""Demo data. Run with `python -m app.seed` (or `docker compose exec api python -m app.seed`).

Idempotent: does nothing if any user already exists. Checkouts, plans and payments go through the
real services (with back-dated `now`), so every number matches the business logic.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import (
    MerchantProfile,
    MerchantProgram,
    MerchantStatus,
    PaymentMethod,
    PaymentMethodKind,
    PaymentSource,
    Plan,
    Product,
    Transaction,
    TransactionStatus,
    User,
    UserRole,
    utcnow,
)
from app.services import orders
from app.services.decisioning import decide, ensure_risk_tiers, run_credit_check
from app.services.payments import apply_payment
from app.services.plans import select_plan

DEMO_PASSWORD = "Password123!"
D = Decimal


def seed(db: Session) -> bool:
    ensure_risk_tiers(db)
    if db.scalar(select(User.id).limit(1)) is not None:
        db.commit()
        return False

    hashed = hash_password(DEMO_PASSWORD)
    now = utcnow()

    def days_ago(n: int) -> datetime:
        return now - timedelta(days=n)

    def user(email: str, name: str, role: UserRole) -> User:
        u = User(email=email, full_name=name, hashed_password=hashed, role=role, created_at=days_ago(200))
        db.add(u)
        db.flush()
        return u

    def merchant(email: str, name: str, business: str, status: MerchantStatus,
                 programs: list[tuple[int, bool, str, str]], products: list[tuple[str, str]]) -> dict[str, Product]:
        owner = user(email, name, UserRole.merchant)
        owner.merchant_profile = MerchantProfile(business_name=business, status=status, created_at=days_ago(200),
                                                 reviewed_at=days_ago(190) if status == MerchantStatus.active else None)
        db.flush()
        for term, promo, lo, hi in programs:
            db.add(MerchantProgram(merchant_id=owner.id, term_months=term, zero_apr_promo=promo,
                                   min_amount=D(lo), max_amount=D(hi), created_at=days_ago(190)))
        catalog = {name: Product(merchant_id=owner.id, name=name, price=D(price), created_at=days_ago(190))
                   for name, price in products}
        db.add_all(catalog.values())
        db.flush()
        db.refresh(owner.merchant_profile)  # load the programs just added
        return catalog

    def consumer(email: str, name: str, score: int, *methods: tuple[PaymentMethodKind, str, str]) -> User:
        u = user(email, name, UserRole.consumer)
        run_credit_check(db, u, score=score, now=days_ago(150))
        for i, (kind, label, last4) in enumerate(methods):
            db.add(PaymentMethod(user_id=u.id, kind=kind, label=label, last4=last4, is_default=i == 0,
                                 created_at=days_ago(150)))
        db.flush()
        return u

    def purchase(buyer: User, product: Product, at: datetime) -> Transaction:
        tx = Transaction(consumer_id=buyer.id, merchant_id=product.merchant_id, merchant=product.merchant,
                         consumer=buyer, product=product, amount=product.price,
                         status=TransactionStatus.in_review, created_at=at)
        check = run_credit_check(db, buyer, now=at)
        decide(db, tx, check, at)
        db.add(tx)
        db.flush()
        return tx

    def finance(buyer: User, product: Product, term: int, at: datetime, *, autopay: bool = False,
                capture: bool = True) -> Plan:
        tx = purchase(buyer, product, at)
        assert tx.status == TransactionStatus.approved, (buyer.email, product.name, tx.decision_reason)
        method = db.scalar(select(PaymentMethod).where(PaymentMethod.user_id == buyer.id,
                                                       PaymentMethod.is_default.is_(True)))
        plan = select_plan(db, tx, term, agree=True, autopay_enabled=autopay and method is not None,
                           payment_method=method, now=at)
        if capture:
            orders.capture(db, tx, now=at + timedelta(days=1))
        return plan

    def pay_installments(plan: Plan, count: int) -> None:
        for inst in plan.installments[:count]:
            apply_payment(plan, inst.amount_remaining, datetime.combine(inst.due_date, now.timetz()),
                          payment_method_id=plan.payment_method_id,
                          source=PaymentSource.autopay if plan.autopay_enabled else PaymentSource.manual)

    user("admin@demo.com", "Avery Admin", UserRole.admin)

    shop = merchant(
        "shop@demo.com", "Sam Park", "Demo Electronics", MerchantStatus.active,
        programs=[(3, True, "50", "3000"), (6, False, "50", "30000"), (12, False, "200", "30000"),
                  (24, False, "500", "30000")],
        products=[("Wireless Headphones", "120.00"), ("Laptop Pro 14", "1000.00"), ("Smartwatch", "299.00"),
                  ("4K Monitor", "380.00"), ("Tablet", "450.00"), ("Gaming Console", "499.00"),
                  ("Camera Kit", "1850.00")],
    )
    home = merchant(
        "home@demo.com", "Hana Kim", "Cozy Home", MerchantStatus.active,
        programs=[(6, False, "50", "30000"), (12, True, "500", "5000"), (24, False, "1000", "30000")],
        products=[("Sectional Sofa", "2400.00"), ("Desk Chair", "350.00"), ("Dining Table", "1200.00"),
                  ("Bed Frame", "900.00"), ("Floor Lamp", "80.00")],
    )
    merchant(
        "newshop@demo.com", "Nico Ruiz", "Fresh Outdoors", MerchantStatus.pending, programs=[],
        products=[("4-Person Tent", "320.00"), ("Mountain Bike", "1400.00")],
    )

    bank, card = PaymentMethodKind.bank, PaymentMethodKind.card
    alice = consumer("alice@demo.com", "Alice Chen", 780, (bank, "Chase Checking", "1234"), (card, "Visa Debit", "4242"))
    consumer("bob@demo.com", "Bob Martinez", 665)
    carol = consumer("carol@demo.com", "Carol Diaz", 615, (bank, "Wells Fargo Checking", "5678"))
    dave = consumer("dave@demo.com", "Dave Wilson", 560)
    erin = consumer("erin@demo.com", "Erin Brooks", 705, (card, "Mastercard Debit", "8888"))

    # Alice: a 0% plan paid off early, a current 12-month plan on autopay, a 24-month plan that is
    # ~45 days late (no autopay), and an order the merchant still has to capture.
    paid_off = finance(alice, shop["Wireless Headphones"], 3, days_ago(120))
    apply_payment(paid_off, paid_off.remaining_balance, days_ago(60), payment_method_id=None)
    current = finance(alice, shop["Laptop Pro 14"], 12, days_ago(65), autopay=True)
    pay_installments(current, 2)
    finance(alice, home["Sectional Sofa"], 24, days_ago(75))
    finance(alice, shop["Smartwatch"], 6, days_ago(1), autopay=True, capture=False)

    # Erin: first installment of a 0% promo plan ~10 days late.
    finance(erin, home["Bed Frame"], 12, days_ago(40))

    # Carol is in the manual-review band; Dave gets declined.
    purchase(carol, home["Desk Chair"], days_ago(2))
    purchase(dave, shop["Laptop Pro 14"], days_ago(3))

    db.commit()
    return True


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        created = seed(db)
    if created:
        print(f"Seeded demo data. Accounts (password {DEMO_PASSWORD}):")
        print("  admin:     admin@demo.com")
        print("  merchants: shop@demo.com, home@demo.com (active), newshop@demo.com (pending)")
        print("  consumers: alice@demo.com (780), bob@demo.com (665), carol@demo.com (615, review),")
        print("             dave@demo.com (560, declined), erin@demo.com (705)")
    else:
        print("Users already exist; skipped demo data (risk tiers ensured).")


if __name__ == "__main__":
    main()
