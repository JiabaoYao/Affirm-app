"""End-to-end flow from README §8, against an in-memory database."""

from decimal import Decimal

PASSWORD = "Password123!"


def register(client, email, role):
    r = client.post("/auth/register", json={"email": email, "password": PASSWORD, "role": role})
    assert r.status_code == 201, r.text
    return r.json()


def login(client, email):
    r = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def setup_checkout(client, price="1000.00"):
    register(client, "shop@demo.com", "merchant")
    register(client, "alice@demo.com", "consumer")
    shop, alice = login(client, "shop@demo.com"), login(client, "alice@demo.com")
    product = client.post("/products", json={"name": "Laptop", "price": price}, headers=shop).json()
    r = client.post("/transactions", json={"customer_email": "alice@demo.com", "product_id": product["id"]},
                    headers=shop)
    assert r.status_code == 201, r.text
    return shop, alice, r.json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_auth_errors(client):
    register(client, "alice@demo.com", "consumer")

    dup = client.post("/auth/register", json={"email": "ALICE@demo.com", "password": PASSWORD})
    assert (dup.status_code, dup.json()["code"]) == (409, "EMAIL_TAKEN")

    bad = client.post("/auth/login", data={"username": "alice@demo.com", "password": "wrong-password"})
    assert (bad.status_code, bad.json()["code"]) == (401, "INVALID_CREDENTIALS")

    missing = client.get("/plans")
    assert (missing.status_code, missing.json()["code"]) == (401, "NOT_AUTHENTICATED")

    garbage = client.get("/plans", headers={"Authorization": "Bearer not-a-jwt"})
    assert (garbage.status_code, garbage.json()["code"]) == (401, "INVALID_TOKEN")


def test_full_installment_flow(client):
    shop, alice, tx = setup_checkout(client)
    assert tx["status"] == "pending_plan" and tx["amount"] == "1000.00"

    # Consumer lists pending purchases; merchant fee is hidden from consumers.
    listed = client.get("/transactions", params={"status": "pending_plan"}, headers=alice).json()
    assert listed["total"] == 1 and listed["items"][0]["service_fee"] is None

    # Compare plans: all 4 offers since amount >= $500.
    options = client.get(f"/transactions/{tx['id']}/plan-options", headers=alice).json()["options"]
    assert [o["term_months"] for o in options] == [3, 6, 12, 24]
    assert options[2] == {"term_months": 12, "apr": "0.1500", "monthly_payment": "90.26",
                          "total_interest": "83.10", "total_cost": "1083.10"}

    # Select the 12-month plan.
    r = client.post(f"/transactions/{tx['id']}/plan", json={"term_months": 12, "autopay_day": 15}, headers=alice)
    assert r.status_code == 201, r.text
    plan = r.json()
    assert len(plan["installments"]) == 12 and plan["remaining_balance"] == "1083.10"

    again = client.post(f"/transactions/{tx['id']}/plan", json={"term_months": 12}, headers=alice)
    assert (again.status_code, again.json()["code"]) == (409, "PLAN_ALREADY_SELECTED")

    # Merchant now sees the 3% fee.
    merchant_view = client.get(f"/transactions/{tx['id']}", headers=shop).json()
    assert merchant_view["status"] == "financed" and merchant_view["service_fee"] == "30.00"

    # Autopay day.
    patched = client.patch(f"/plans/{plan['id']}", json={"autopay_day": 1}, headers=alice).json()
    assert all(i["due_date"].endswith("-01") for i in patched["installments"])
    bad_day = client.patch(f"/plans/{plan['id']}", json={"autopay_day": 31}, headers=alice)
    assert (bad_day.status_code, bad_day.json()["code"]) == (422, "VALIDATION_ERROR")

    # Payments.
    paid = client.post(f"/plans/{plan['id']}/payments", json={"amount": "150.00"}, headers=alice).json()
    assert paid["remaining_balance"] == "933.10" and paid["plan_status"] == "active"
    detail = client.get(f"/plans/{plan['id']}", headers=alice).json()
    assert [i["status"] for i in detail["installments"][:3]] == ["paid", "partial", "pending"]

    over = client.post(f"/plans/{plan['id']}/payments", json={"amount": "5000.00"}, headers=alice)
    assert (over.status_code, over.json()["code"]) == (400, "OVERPAYMENT")
    zero = client.post(f"/plans/{plan['id']}/payments", json={"amount": "0"}, headers=alice)
    assert zero.status_code == 422

    final = client.post(f"/plans/{plan['id']}/payments", json={"amount": "933.10"}, headers=alice).json()
    assert final["plan_status"] == "paid_off" and Decimal(final["remaining_balance"]) == 0
    after = client.post(f"/plans/{plan['id']}/payments", json={"amount": "1.00"}, headers=alice)
    assert (after.status_code, after.json()["code"]) == (409, "PLAN_PAID_OFF")

    history = client.get(f"/plans/{plan['id']}/payments", headers=alice).json()
    assert [p["amount"] for p in history] == ["150.00", "933.10"]

    plans = client.get("/plans", params={"status": "paid_off"}, headers=alice).json()
    assert plans["total"] == 1 and plans["items"][0]["next_due_date"] is None


def test_access_control(client):
    shop, alice, tx = setup_checkout(client)
    plan = client.post(f"/transactions/{tx['id']}/plan", json={"term_months": 3}, headers=alice).json()
    register(client, "bob@demo.com", "consumer")
    bob = login(client, "bob@demo.com")

    # Another consumer's resources look like they don't exist.
    r = client.get(f"/plans/{plan['id']}", headers=bob)
    assert (r.status_code, r.json()["code"]) == (404, "PLAN_NOT_FOUND")
    r = client.get(f"/transactions/{tx['id']}", headers=bob)
    assert (r.status_code, r.json()["code"]) == (404, "TRANSACTION_NOT_FOUND")
    assert client.get("/transactions", headers=bob).json()["total"] == 0

    # Wrong role.
    r = client.post("/products", json={"name": "X", "price": "10.00"}, headers=alice)
    assert (r.status_code, r.json()["code"]) == (403, "FORBIDDEN_ROLE")
    r = client.get("/plans", headers=shop)
    assert (r.status_code, r.json()["code"]) == (403, "FORBIDDEN_ROLE")


def test_logout_revokes_token(client):
    register(client, "alice@demo.com", "consumer")
    alice = login(client, "alice@demo.com")

    assert client.post("/auth/logout", headers=alice).status_code == 204
    r = client.get("/auth/me", headers=alice)
    assert (r.status_code, r.json()["code"]) == (401, "TOKEN_REVOKED")


def test_checkout_rules(client):
    shop, alice, _ = setup_checkout(client)
    cheap = client.post("/products", json={"name": "Cable", "price": "20.00"}, headers=shop).json()
    mid = client.post("/products", json={"name": "Chair", "price": "300.00"}, headers=shop).json()

    r = client.post("/transactions", json={"customer_email": "alice@demo.com", "product_id": cheap["id"]},
                    headers=shop)
    assert (r.status_code, r.json()["code"]) == (422, "AMOUNT_OUT_OF_RANGE")
    r = client.post("/transactions", json={"customer_email": "nobody@demo.com", "product_id": mid["id"]},
                    headers=shop)
    assert (r.status_code, r.json()["code"]) == (404, "CUSTOMER_NOT_FOUND")
    r = client.post("/products", json={"name": "Free", "price": "0"}, headers=shop)
    assert r.status_code == 422

    # Under $500: no 24-month option, and choosing it is rejected.
    tx = client.post("/transactions", json={"customer_email": "alice@demo.com", "product_id": mid["id"]},
                     headers=shop).json()
    terms = [o["term_months"] for o in client.get(f"/transactions/{tx['id']}/plan-options", headers=alice)
             .json()["options"]]
    assert terms == [3, 6, 12]
    r = client.post(f"/transactions/{tx['id']}/plan", json={"term_months": 24}, headers=alice)
    assert (r.status_code, r.json()["code"]) == (422, "INVALID_TERM")


def test_list_filters_sort_and_pagination(client):
    shop, alice, _ = setup_checkout(client)
    for name, price in [("A", "100.00"), ("B", "700.00"), ("C", "250.00")]:
        p = client.post("/products", json={"name": name, "price": price}, headers=shop).json()
        client.post("/transactions", json={"customer_email": "alice@demo.com", "product_id": p["id"]}, headers=shop)

    page = client.get("/transactions", params={"sort": "amount", "size": 2, "page": 1}, headers=alice).json()
    assert page["total"] == 4 and [t["amount"] for t in page["items"]] == ["100.00", "250.00"]
    page2 = client.get("/transactions", params={"sort": "amount", "size": 2, "page": 2}, headers=alice).json()
    assert [t["amount"] for t in page2["items"]] == ["700.00", "1000.00"]

    ranged = client.get("/transactions", params={"min_amount": 200, "max_amount": 800}, headers=alice).json()
    assert sorted(t["amount"] for t in ranged["items"]) == ["250.00", "700.00"]

    products = client.get("/products", params={"q": "lap"}, headers=shop).json()
    assert [p["name"] for p in products["items"]] == ["Laptop"]

    bad = client.get("/transactions", params={"size": 500}, headers=alice)
    assert bad.status_code == 422


def test_seed_is_idempotent(session_factory):
    from app.models import Plan, PlanStatus, User
    from app.seed import seed

    with session_factory() as db:
        assert seed(db) is True
    with session_factory() as db:
        assert seed(db) is False
        assert db.query(User).count() == 3
        assert sorted(p.status for p in db.query(Plan)) == [PlanStatus.active, PlanStatus.paid_off]
