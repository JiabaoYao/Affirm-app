"""End-to-end flows against an in-memory database: onboarding, checkout, decision, capture, servicing."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.security import hash_password
from app.models import User, UserRole
from app.services.decisioning import run_credit_check

PASSWORD = "Password123!"


def register(client, email, role="consumer", **extra):
    body = {"email": email, "password": PASSWORD, "full_name": email.split("@")[0].title(), "role": role, **extra}
    r = client.post("/auth/register", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def login(client, email):
    r = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin(client, session_factory):
    with session_factory() as db:
        db.add(User(email="admin@demo.com", full_name="Admin", hashed_password=hash_password(PASSWORD),
                    role=UserRole.admin))
        db.commit()
    return login(client, "admin@demo.com")


def set_score(session_factory, email, score):
    """The mock bureau is hash-based; tests pin a score so the tier is known."""
    with session_factory() as db:
        user = db.query(User).filter_by(email=email).one()
        run_credit_check(db, user, score=score)
        db.commit()


def consumer(client, session_factory, email, score):
    register(client, email)
    set_score(session_factory, email, score)
    return login(client, email)


def active_merchant(client, admin, email="shop@demo.com", business="Demo Electronics",
                    programs=((3, True), (6, False), (12, False), (24, False))):
    user = register(client, email, "merchant", business_name=business)
    r = client.post(f"/admin/merchants/{user['id']}/approve", json={}, headers=admin)
    assert r.status_code == 200, r.text
    headers = login(client, email)
    for term, promo in programs:
        r = client.post("/merchant/programs", json={"term_months": term, "zero_apr_promo": promo}, headers=headers)
        assert r.status_code == 201, r.text
    return headers


def product(client, merchant, name="Laptop", price="1000.00"):
    r = client.post("/products", json={"name": name, "price": price}, headers=merchant)
    assert r.status_code == 201, r.text
    return r.json()


def checkout(client, headers, product_id, quantity=1):
    r = client.post("/transactions", json={"product_id": product_id, "quantity": quantity}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def add_method(client, headers, **body):
    r = client.post("/payment-methods", json={"kind": "bank", "label": "Checking", "last4": "1234", **body},
                    headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_auth_errors(client):
    register(client, "alice@demo.com")

    dup = client.post("/auth/register", json={"email": "ALICE@demo.com", "password": PASSWORD, "full_name": "A"})
    assert (dup.status_code, dup.json()["code"]) == (409, "EMAIL_TAKEN")

    as_admin = client.post("/auth/register", json={"email": "x@demo.com", "password": PASSWORD, "full_name": "X",
                                                   "role": "admin"})
    assert (as_admin.status_code, as_admin.json()["code"]) == (422, "VALIDATION_ERROR")
    no_business = client.post("/auth/register", json={"email": "m@demo.com", "password": PASSWORD,
                                                      "full_name": "M", "role": "merchant"})
    assert no_business.status_code == 422

    bad = client.post("/auth/login", data={"username": "alice@demo.com", "password": "wrong-password"})
    assert (bad.status_code, bad.json()["code"]) == (401, "INVALID_CREDENTIALS")

    missing = client.get("/plans")
    assert (missing.status_code, missing.json()["code"]) == (401, "NOT_AUTHENTICATED")

    garbage = client.get("/plans", headers={"Authorization": "Bearer not-a-jwt"})
    assert (garbage.status_code, garbage.json()["code"]) == (401, "INVALID_TOKEN")


def test_logout_revokes_token(client):
    register(client, "alice@demo.com")
    alice = login(client, "alice@demo.com")

    assert client.post("/auth/logout", headers=alice).status_code == 204
    r = client.get("/auth/me", headers=alice)
    assert (r.status_code, r.json()["code"]) == (401, "TOKEN_REVOKED")


def test_merchant_onboarding(client, admin):
    user = register(client, "new@demo.com", "merchant", business_name="New Shop")
    assert user["merchant_status"] == "pending" and user["business_name"] == "New Shop"
    shop = login(client, "new@demo.com")

    r = client.post("/products", json={"name": "Tent", "price": "300.00"}, headers=shop)
    assert (r.status_code, r.json()["code"]) == (403, "MERCHANT_NOT_ACTIVE")
    assert client.get("/admin/merchants", params={"status": "pending"}, headers=admin).json()["total"] == 1

    r = client.post(f"/admin/merchants/{user['id']}/approve", json={"fee_rate": "0.0250"}, headers=admin)
    assert r.json()["status"] == "active" and r.json()["fee_rate"] == "0.0250"
    again = client.post(f"/admin/merchants/{user['id']}/approve", json={}, headers=admin)
    assert (again.status_code, again.json()["code"]) == (409, "ALREADY_ACTIVE")

    product(client, shop, "Tent", "300.00")
    note = client.get("/notifications", headers=shop).json()
    assert note["unread"] == 1 and note["items"][0]["kind"] == "merchant_approved"

    # Suspended merchants disappear from the store.
    register(client, "alice@demo.com")
    alice = login(client, "alice@demo.com")
    assert client.get("/store/products", headers=alice).json()["total"] == 1
    client.post(f"/admin/merchants/{user['id']}/suspend", headers=admin)
    assert client.get("/store/products", headers=alice).json()["total"] == 0
    audit = client.get("/admin/audit-log", headers=admin).json()
    assert [a["action"] for a in audit["items"]] == ["merchant.suspend", "merchant.approve"]


def test_full_checkout_and_loan_flow(client, session_factory, admin):
    shop = active_merchant(client, admin)
    laptop = product(client, shop)
    alice = consumer(client, session_factory, "alice@demo.com", 780)

    store = client.get("/store/products", headers=alice).json()["items"][0]
    assert store["merchant_name"] == "Demo Electronics" and store["has_zero_apr"] is True
    assert store["as_low_as_monthly"] == "46.14" and store["as_low_as_term"] == 24

    tx = checkout(client, alice, laptop["id"])
    assert (tx["status"], tx["credit_score"], tx["risk_tier"], tx["merchant_fee"]) == ("approved", 780, "A", None)

    options = client.get(f"/transactions/{tx['id']}/plan-options", headers=alice).json()
    assert options["risk_tier"] == "A"
    assert [o["term_months"] for o in options["options"]] == [3, 6, 12, 24]
    assert options["options"][0]["apr"] == "0.0000" and options["options"][0]["zero_apr_promo"] is True
    assert options["options"][2] == {"term_months": 12, "apr": "0.1000", "zero_apr_promo": False,
                                     "monthly_payment": "87.92", "total_interest": "54.99", "total_cost": "1054.99"}

    url = f"/transactions/{tx['id']}/plan"
    r = client.post(url, json={"term_months": 12, "agree": False}, headers=alice)
    assert (r.status_code, r.json()["code"]) == (422, "AGREEMENT_REQUIRED")
    r = client.post(url, json={"term_months": 12, "agree": True, "autopay_enabled": True}, headers=alice)
    assert (r.status_code, r.json()["code"]) == (422, "PAYMENT_METHOD_REQUIRED")

    method = add_method(client, alice)
    assert method["is_default"] is True
    r = client.post(url, json={"term_months": 12, "agree": True, "autopay_enabled": True, "autopay_day": 15},
                    headers=alice)
    assert r.status_code == 201, r.text
    plan = r.json()
    assert plan["status"] == "pending_capture" and plan["payment_method_id"] == method["id"]
    assert len(plan["installments"]) == 12 and plan["remaining_balance"] == "1054.99"
    again = client.post(url, json={"term_months": 12, "agree": True}, headers=alice)
    assert (again.status_code, again.json()["code"]) == (409, "PLAN_ALREADY_SELECTED")

    early = client.post(f"/plans/{plan['id']}/payments", json={"amount": "50.00"}, headers=alice)
    assert (early.status_code, early.json()["code"]) == (409, "PLAN_NOT_ACTIVE")

    # Merchant sees the order and its 3% fee, but not the consumer's credit data.
    order = client.get(f"/transactions/{tx['id']}", headers=shop).json()
    assert (order["status"], order["merchant_fee"], order["credit_score"]) == ("authorized", "30.00", None)
    r = client.post(f"/transactions/{tx['id']}/capture", headers=shop)
    assert r.json()["status"] == "captured"
    assert client.patch(f"/transactions/{tx['id']}", json={"tracking_number": "1Z999"},
                        headers=shop).json()["tracking_number"] == "1Z999"
    summary = client.get("/merchant/summary", headers=shop).json()
    assert (summary["gross_volume"], summary["fees"], summary["net_payout"]) == ("1000.00", "30.00", "970.00")

    notes = client.get("/notifications", headers=alice).json()
    assert notes["items"][0]["kind"] == "order_captured"

    # Autopay day, then payments until paid off.
    patched = client.patch(f"/plans/{plan['id']}", json={"autopay_day": 1}, headers=alice).json()
    assert patched["status"] == "active" and all(i["due_date"].endswith("-01") for i in patched["installments"])
    paid = client.post(f"/plans/{plan['id']}/payments", json={"amount": "150.00"}, headers=alice).json()
    assert paid["remaining_balance"] == "904.99" and paid["payment_method_id"] == method["id"]
    detail = client.get(f"/plans/{plan['id']}", headers=alice).json()
    assert [i["status"] for i in detail["installments"][:3]] == ["paid", "partial", "pending"]

    over = client.post(f"/plans/{plan['id']}/payments", json={"amount": "5000.00"}, headers=alice)
    assert (over.status_code, over.json()["code"]) == (400, "OVERPAYMENT")
    final = client.post(f"/plans/{plan['id']}/payments", json={"amount": "904.99"}, headers=alice).json()
    assert final["plan_status"] == "paid_off" and Decimal(final["remaining_balance"]) == 0
    after = client.post(f"/plans/{plan['id']}/payments", json={"amount": "1.00"}, headers=alice)
    assert (after.status_code, after.json()["code"]) == (409, "PLAN_PAID_OFF")
    history = client.get(f"/plans/{plan['id']}/payments", headers=alice).json()
    assert [p["amount"] for p in history] == ["150.00", "904.99"]


def test_risk_tiers_shape_the_offers(client, session_factory, admin):
    shop = active_merchant(client, admin)
    laptop = product(client, shop)
    bob = consumer(client, session_factory, "bob@demo.com", 665)

    tx = checkout(client, bob, laptop["id"])
    options = client.get(f"/transactions/{tx['id']}/plan-options", headers=bob).json()
    assert options["risk_tier"] == "C"
    # Tier C: max 12 months, 28% APR, but the merchant's 3-month promo is still 0%.
    assert [(o["term_months"], o["apr"]) for o in options["options"]] == [(3, "0.0000"), (6, "0.2800"),
                                                                           (12, "0.2800")]
    r = client.post(f"/transactions/{tx['id']}/plan", json={"term_months": 24, "agree": True}, headers=bob)
    assert (r.status_code, r.json()["code"]) == (422, "INVALID_TERM")

    # Admin raises tier C's APR: new quotes change.
    tier_c = next(t for t in client.get("/admin/risk-tiers", headers=admin).json() if t["name"] == "C")
    client.patch(f"/admin/risk-tiers/{tier_c['id']}", json={"apr": "0.2000"}, headers=admin)
    options = client.get(f"/transactions/{tx['id']}/plan-options", headers=bob).json()["options"]
    assert options[1]["apr"] == "0.2000"

    # Over the tier's $2,500 limit: declined with a reason.
    camera = product(client, shop, "Camera", "3000.00")
    declined = checkout(client, bob, camera["id"])
    assert declined["status"] == "declined" and "spending power" in declined["decision_reason"]
    credit = client.get("/credit/me", headers=bob).json()
    assert (credit["score"], credit["risk_tier"], credit["spending_power"]) == (665, "C", "2500.00")


def test_decline_and_manual_review(client, session_factory, admin):
    shop = active_merchant(client, admin)
    laptop = product(client, shop)
    dave = consumer(client, session_factory, "dave@demo.com", 560)
    carol = consumer(client, session_factory, "carol@demo.com", 615)

    declined = checkout(client, dave, laptop["id"])
    assert declined["status"] == "declined" and "560" in declined["decision_reason"]
    r = client.get(f"/transactions/{declined['id']}/plan-options", headers=dave)
    assert (r.status_code, r.json()["code"]) == (409, "NOT_APPROVED")

    flagged = checkout(client, carol, laptop["id"])
    assert flagged["status"] == "in_review"
    queue = client.get("/admin/reviews", headers=admin).json()
    assert [t["id"] for t in queue["items"]] == [flagged["id"]] and queue["items"][0]["credit_score"] == 615

    r = client.post(f"/admin/reviews/{flagged['id']}/approve", json={"reason": "Verified income"}, headers=admin)
    assert r.json()["status"] == "approved"
    options = client.get(f"/transactions/{flagged['id']}/plan-options", headers=carol).json()["options"]
    assert [o["term_months"] for o in options] == [3, 6, 12]

    second = checkout(client, carol, laptop["id"])
    client.post(f"/admin/reviews/{second['id']}/decline", json={"reason": "Identity not verified."}, headers=admin)
    assert client.get(f"/transactions/{second['id']}", headers=carol).json()["decision_reason"] == "Identity not verified."
    again = client.post(f"/admin/reviews/{second['id']}/approve", headers=admin)
    assert (again.status_code, again.json()["code"]) == (409, "NOT_IN_REVIEW")

    metrics = client.get("/admin/metrics", headers=admin).json()
    assert (metrics["applications"], metrics["approved"], metrics["declined"]) == (3, 1, 2)


def test_void_and_cancel(client, session_factory, admin):
    shop = active_merchant(client, admin)
    laptop = product(client, shop)
    alice = consumer(client, session_factory, "alice@demo.com", 780)

    tx = checkout(client, alice, laptop["id"])
    plan = client.post(f"/transactions/{tx['id']}/plan", json={"term_months": 3, "agree": True}, headers=alice).json()
    voided = client.post(f"/transactions/{tx['id']}/void", headers=shop).json()
    assert voided["status"] == "voided" and voided["merchant_fee"] is None
    assert client.get(f"/plans/{plan['id']}", headers=alice).json()["status"] == "voided"
    r = client.post(f"/transactions/{tx['id']}/capture", headers=shop)
    assert (r.status_code, r.json()["code"]) == (409, "INVALID_ORDER_STATE")

    other = checkout(client, alice, laptop["id"])
    assert client.post(f"/transactions/{other['id']}/cancel", headers=alice).json()["status"] == "cancelled"
    r = client.post(f"/transactions/{other['id']}/plan", json={"term_months": 3, "agree": True}, headers=alice)
    assert (r.status_code, r.json()["code"]) == (409, "NOT_APPROVED")


def test_merchant_programs(client, session_factory, admin):
    shop = active_merchant(client, admin, programs=((6, False),))
    chair = product(client, shop, "Chair", "300.00")
    alice = consumer(client, session_factory, "alice@demo.com", 780)

    dup = client.post("/merchant/programs", json={"term_months": 6}, headers=shop)
    assert (dup.status_code, dup.json()["code"]) == (409, "PROGRAM_EXISTS")
    bad = client.post("/merchant/programs", json={"term_months": 12, "min_amount": "900", "max_amount": "100"},
                      headers=shop)
    assert bad.status_code == 422
    promo = client.post("/merchant/programs", json={"term_months": 12, "zero_apr_promo": True, "min_amount": "500.00"},
                        headers=shop).json()

    # $300 is under the promo's $500 minimum.
    tx = checkout(client, alice, chair["id"])
    terms = [o["term_months"] for o in client.get(f"/transactions/{tx['id']}/plan-options", headers=alice)
             .json()["options"]]
    assert terms == [6]
    client.patch(f"/merchant/programs/{promo['id']}", json={"min_amount": "100.00"}, headers=shop)
    plan = client.post(f"/transactions/{tx['id']}/plan", json={"term_months": 12, "agree": True}, headers=alice).json()
    assert plan["apr"] == "0.0000" and plan["zero_apr_promo"] is True
    # Promo orders carry the extra 3% promo fee: 300 * 6% = 18.
    assert client.get(f"/transactions/{tx['id']}", headers=shop).json()["merchant_fee"] == "18.00"

    # Without any program that fits, checkout is declined.
    for p in client.get("/merchant/programs", headers=shop).json():
        client.patch(f"/merchant/programs/{p['id']}", json={"active": False}, headers=shop)
    assert checkout(client, alice, chair["id"])["status"] == "declined"


def test_payment_methods(client, session_factory, admin):
    alice = consumer(client, session_factory, "alice@demo.com", 780)
    first = add_method(client, alice)
    second = add_method(client, alice, kind="card", label="Visa", last4="4242", is_default=True)
    methods = client.get("/payment-methods", headers=alice).json()
    assert [(m["id"], m["is_default"]) for m in methods] == [(second["id"], True), (first["id"], False)]

    bad = client.post("/payment-methods", json={"kind": "card", "label": "X", "last4": "12"}, headers=alice)
    assert bad.status_code == 422
    assert client.delete(f"/payment-methods/{second['id']}", headers=alice).status_code == 204
    methods = client.get("/payment-methods", headers=alice).json()
    assert [(m["id"], m["is_default"]) for m in methods] == [(first["id"], True)]


def test_daily_job_autopay_and_delinquency(client, session_factory, admin):
    shop = active_merchant(client, admin)
    laptop = product(client, shop)
    alice = consumer(client, session_factory, "alice@demo.com", 780)
    erin = consumer(client, session_factory, "erin@demo.com", 700)
    add_method(client, alice)

    plans = {}
    for name, headers, autopay in (("alice", alice, True), ("erin", erin, False)):
        tx = checkout(client, headers, laptop["id"])
        plans[name] = client.post(f"/transactions/{tx['id']}/plan",
                                  json={"term_months": 6, "agree": True, "autopay_enabled": autopay},
                                  headers=headers).json()
        client.post(f"/transactions/{tx['id']}/capture", headers=shop)

    first_due = date.fromisoformat(plans["alice"]["installments"][0]["due_date"])
    r = client.post("/admin/jobs/run-daily", json={"as_of": str(first_due + timedelta(days=5))}, headers=admin).json()
    assert (r["autopay_payments"], r["overdue_notices"]) == (1, 1)
    alice_plan = client.get(f"/plans/{plans['alice']['id']}", headers=alice).json()
    assert alice_plan["installments"][0]["status"] == "paid"
    assert client.get(f"/plans/{plans['alice']['id']}/payments", headers=alice).json()[0]["source"] == "autopay"
    assert client.get("/notifications", headers=erin).json()["items"][0]["kind"] == "overdue"

    # Running again doesn't double-charge or re-notify.
    r = client.post("/admin/jobs/run-daily", json={"as_of": str(first_due + timedelta(days=5))}, headers=admin).json()
    assert (r["autopay_payments"], r["overdue_notices"]) == (0, 0)

    # Delinquency uses the real date, so nothing is late yet.
    assert client.get("/admin/delinquency", headers=admin).json() == []


def test_access_control(client, session_factory, admin):
    shop = active_merchant(client, admin)
    other_shop = active_merchant(client, admin, "home@demo.com", "Cozy Home", programs=())
    laptop = product(client, shop)
    alice = consumer(client, session_factory, "alice@demo.com", 780)
    bob = consumer(client, session_factory, "bob@demo.com", 780)
    tx = checkout(client, alice, laptop["id"])
    plan = client.post(f"/transactions/{tx['id']}/plan", json={"term_months": 3, "agree": True}, headers=alice).json()

    # Another user's resources look like they don't exist.
    r = client.get(f"/plans/{plan['id']}", headers=bob)
    assert (r.status_code, r.json()["code"]) == (404, "PLAN_NOT_FOUND")
    r = client.get(f"/transactions/{tx['id']}", headers=bob)
    assert (r.status_code, r.json()["code"]) == (404, "TRANSACTION_NOT_FOUND")
    r = client.post(f"/transactions/{tx['id']}/capture", headers=other_shop)
    assert (r.status_code, r.json()["code"]) == (404, "TRANSACTION_NOT_FOUND")
    assert client.get("/transactions", headers=bob).json()["total"] == 0
    assert client.get("/transactions", headers=admin).json()["total"] == 1

    # Wrong role.
    for method, url, headers in (("post", "/products", alice), ("get", "/plans", shop),
                                 ("get", "/admin/metrics", alice), ("get", "/admin/metrics", shop),
                                 ("post", f"/transactions/{tx['id']}/capture", alice)):
        r = getattr(client, method)(url, headers=headers, **({"json": {}} if method == "post" else {}))
        assert (r.status_code, r.json()["code"]) == (403, "FORBIDDEN_ROLE"), url


def test_list_filters_sort_and_pagination(client, session_factory, admin):
    shop = active_merchant(client, admin)
    alice = consumer(client, session_factory, "alice@demo.com", 780)
    for name, price in [("A", "100.00"), ("B", "700.00"), ("C", "250.00"), ("D", "1000.00")]:
        checkout(client, alice, product(client, shop, name, price)["id"])

    page = client.get("/transactions", params={"sort": "amount", "size": 2, "page": 1}, headers=alice).json()
    assert page["total"] == 4 and [t["amount"] for t in page["items"]] == ["100.00", "250.00"]
    page2 = client.get("/transactions", params={"sort": "amount", "size": 2, "page": 2}, headers=alice).json()
    assert [t["amount"] for t in page2["items"]] == ["700.00", "1000.00"]

    ranged = client.get("/transactions", params={"min_amount": 200, "max_amount": 800}, headers=alice).json()
    assert sorted(t["amount"] for t in ranged["items"]) == ["250.00", "700.00"]
    approved = client.get("/transactions", params=[("status", "approved"), ("status", "declined")],
                          headers=alice).json()
    assert approved["total"] == 4

    products = client.get("/store/products", params={"q": "b", "sort": "-price"}, headers=alice).json()
    assert [p["name"] for p in products["items"]] == ["B"]

    bad = client.get("/transactions", params={"size": 500}, headers=alice)
    assert bad.status_code == 422


def test_quantity_multiplies_the_financed_amount(client, session_factory, admin):
    shop = active_merchant(client, admin)
    tablet = product(client, shop, "Tablet", "450.00")
    bob = consumer(client, session_factory, "bob@demo.com", 665)  # tier C: $2,500 limit

    tx = checkout(client, bob, tablet["id"], quantity=3)
    assert (tx["status"], tx["quantity"], tx["amount"]) == ("approved", 3, "1350.00")
    plan = client.post(f"/transactions/{tx['id']}/plan", json={"term_months": 3, "agree": True}, headers=bob).json()
    assert (plan["principal"], plan["quantity"]) == ("1350.00", 3)
    order = client.get(f"/transactions/{tx['id']}", headers=shop).json()
    assert (order["quantity"], order["merchant_fee"]) == (3, "81.00")  # 3% + 3% promo on $1,350

    # 6 × $450 = $2,700 is over what's left of the $2,500 limit.
    over = checkout(client, bob, tablet["id"], quantity=6)
    assert over["status"] == "declined" and "spending power" in over["decision_reason"]
    for bad in (0, 11):
        r = client.post("/transactions", json={"product_id": tablet["id"], "quantity": bad}, headers=bob)
        assert r.status_code == 422


def test_seed_is_idempotent(session_factory):
    from app.models import Plan, PlanStatus, Transaction, TransactionStatus
    from app.seed import seed

    with session_factory() as db:
        assert seed(db) is True
    with session_factory() as db:
        assert seed(db) is False
        assert db.query(User).count() == 9
        assert sorted(p.status.value for p in db.query(Plan)) == sorted(
            [PlanStatus.paid_off, PlanStatus.active, PlanStatus.active, PlanStatus.active,
             PlanStatus.pending_capture])
        statuses = {t.status for t in db.query(Transaction)}
        assert {TransactionStatus.in_review, TransactionStatus.declined, TransactionStatus.authorized} <= statuses
        late = [p for p in db.query(Plan) if p.days_past_due > 0]
        assert sorted(p.days_past_due > 30 for p in late) == [False, True]
