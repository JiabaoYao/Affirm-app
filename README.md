# Affirm-style Installment Plan API

A backend MVP, modeled on affirm.com, for **installment plan selection & management**.
Stack: Python · FastAPI · PostgreSQL · SQLAlchemy · JWT · Docker · AWS EC2.

---

## 0. Proposal (as submitted)
```
Website: affirm.com

Business domain: Financial services

Core business: Affirm is a buy-now-pay-later platform. Consumers split purchases into installments with transparent upfront pricing and no late fees. Merchants integrate Affirm at checkout to increase conversion and average order value, and pay Affirm fees in return.

Identified needs:
(1) installment plan selection and management,
(2) payment reminders and notifications,
(3) spending-power prequalification

Selected need: Need 1. I'll build a backend API, modeled on Affirm's flow but using my own mock data, where users can record purchases, compare plan options (term, APR, monthly payment, total interest), select a plan, view the amortization schedule, update their autopay date, and record payments.
```

---

## 1. Business Analysis

| Question | Answer |
|---|---|
| Company / domain | Affirm (affirm.com), Financial services, buy-now-pay-later (BNPL) |
| What it does | Lets consumers split a purchase into installments with fixed, upfront pricing (no late fees, no compounding). Merchants offer Affirm at checkout and pay Affirm a fee per financed order. |
| Main users | **Consumers** (finance purchases, manage plans, make payments) and **Merchants** (create checkouts, pay fees) |
| Key user actions | Merchant starts a checkout → consumer compares plan options → selects a plan → views the schedule → sets the autopay day → pays installments until paid off |
| Data collected | Accounts, merchant products, purchases, chosen plans, amortization schedules, payments, merchant fees |
| Why this need matters | Transparent plan choice is Affirm's core value: it drives merchant conversion and consumer trust. Every other feature (reminders, prequalification) depends on plans existing. |

**Privacy / security / access control**
- Passwords hashed with bcrypt and never returned. No card or bank numbers stored (payments are recorded as mock amounts).
- JWTs expire after 60 minutes. Logout revokes the token through a `jti` denylist.
- Each user sees **only their own** records. Requests for someone else's resource return `404`, so their existence isn't revealed.
- Role checks: only merchants create products and transactions; only consumers select plans and pay.
- The merchant fee (`service_fee`) is merchant–Affirm data, so it's returned to merchants only and hidden from consumers.
- Secrets live in `.env` (never committed). Money uses `Numeric(12,2)` / `Decimal`, never `float`.

---

## 2. Roles & Main Flow

```
Merchant                         Consumer
   |  POST /products                 |
   |  POST /transactions  ---------> |  (purchase now "pending_plan")
   |                                 |  GET  /transactions/{id}/plan-options
   |                                 |  POST /transactions/{id}/plan   -> plan + schedule
   |                                 |  GET  /plans/{id}               -> schedule
   |                                 |  PATCH /plans/{id}              -> autopay_day
   |                                 |  POST /plans/{id}/payments      -> until "paid_off"
```

Roles are stored on `users.role` (`consumer` | `merchant`) and carried in the JWT. In the real system merchants are onboarded separately; for this demo, `register` accepts a role.

---

## 3. Data Model

```
users 1──* products            (merchant owns products)
users 1──* transactions        (as consumer, and as merchant)
products 1──* transactions
transactions 1──0..1 plans
plan_offers 1──* plans
plans 1──* installments        (the amortization schedule)
plans 1──* payments
```

| Table | Columns |
|---|---|
| **users** | id, email (unique), hashed_password, role (`consumer`/`merchant`), created_at |
| **products** | id, merchant_id → users, name, price `Numeric(12,2)`, created_at |
| **transactions** | id, consumer_id → users, merchant_id → users, product_id → products, amount `Numeric(12,2)` (copied from price at purchase), status (`pending_plan`/`financed`), service_fee `Numeric(12,2)` nullable (set when financed), created_at |
| **plan_offers** | id, term_months (unique), apr `Numeric(5,4)`, min_amount `Numeric(12,2)`. A seeded lookup table. |
| **plans** | id, user_id → users, transaction_id → transactions (**unique**), offer_id → plan_offers, term_months, apr, principal, monthly_payment, total_interest, amount_paid, autopay_day (1–28), status (`active`/`paid_off`), created_at |
| **installments** | id, plan_id → plans, seq (1..n), due_date, amount_due, principal, interest, amount_paid, status (`pending`/`partial`/`paid`) |
| **payments** | id, plan_id → plans, amount, paid_at |
| **revoked_tokens** | jti (PK), expires_at |

Notes
- `plans` copies `term_months` / `apr` from the offer, so changing an offer later doesn't rewrite existing loans.
- `transactions.consumer_id` and `merchant_id` both point to `users`. A merchant sees transactions it created; a consumer sees transactions made for them.

---

## 4. Business Rules

**Plan offers (seeded)**

| term_months | APR | Available when amount |
|---|---|---|
| 3 | 0% | ≥ $50 |
| 6 | 10% | ≥ $50 |
| 12 | 15% | ≥ $50 |
| 24 | 30% | ≥ $500 |

An offer is available when `amount ≥ plan_offers.min_amount`.

**Purchase limits:** $50 ≤ amount ≤ $30,000, otherwise `422 AMOUNT_OUT_OF_RANGE` at `POST /transactions`. Product `price` must be > 0. A product under $50 can be listed but can't be financed.

**Merchant service fee:** 3% of amount, set on the transaction when a plan is selected (status → `financed`).

**Amortization** (`app/services/amortization.py`, a pure function that is easy to unit test)
- Monthly rate `r = apr / 12`.
- If `apr == 0`: `payment = P / n`.
- Else: `payment = P·r / (1 − (1+r)^−n)`.
- Round `payment` to cents (`ROUND_HALF_UP`). For each month: `interest = round(balance·r)`, `principal = payment − interest`.
- The **last installment absorbs the remaining cents**: principal = remaining balance.
- `total_interest = Σ interest`.
- Example: $1,000 over 12 months at 15% works out to $90.26/mo and $83.10 of total interest (last installment $90.24).
- **Simplification:** interest is fixed when the schedule is created, so paying early doesn't reduce total interest (real Affirm uses simple interest, where it would).

**Due dates:** all dates and timestamps are UTC. `autopay_day` defaults to `min(today.day, 28)`. Installment *k* is due on `autopay_day` in month (**plan creation month** + *k*).

**Selecting a plan** (`POST /transactions/{id}/plan`)
- The transaction must be the caller's (otherwise `404`) and have status `pending_plan` (otherwise `409 PLAN_ALREADY_SELECTED`).
- `term_months` must be an available offer for that amount (otherwise `422 INVALID_TERM`).
- In one DB transaction: create the plan, create the installments, set the transaction to `financed`, and set `service_fee`.
- A double submit is caught by the unique `plans.transaction_id`: `IntegrityError` → rollback → `409 PLAN_ALREADY_SELECTED`.

**Changing autopay:** `autopay_day` must be 1–28. Recompute `due_date` for **unpaid** installments only. `409` if the plan is `paid_off`.

**Payments**
- Lock the plan row (`SELECT … FOR UPDATE`) while applying a payment, so two concurrent payments can't both pass the balance check.
- `0 < amount ≤ remaining balance` (otherwise `400 OVERPAYMENT` / `422`).
- Apply the payment to the **oldest unpaid installment first** and spill over into the next ones, updating `partial`/`paid`.
- Increase `plans.amount_paid`. When the remaining balance is 0, set the plan to `paid_off`.
- `409 PLAN_PAID_OFF` if the plan is already paid off.
- Remaining balance = `principal + total_interest − amount_paid`.

---

## 5. API Contract

All endpoints except `register`/`login` require `Authorization: Bearer <token>`.
`login` uses `OAuth2PasswordRequestForm`, so the Swagger **Authorize** button works.

### 5.1 Auth (not counted as business endpoints)
| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/auth/register` | `{email, password, role}` | `201` user (no password) | `409 EMAIL_TAKEN`, `422` |
| POST | `/auth/login` | form: `username`, `password` | `200 {access_token, token_type:"bearer"}` | `401 INVALID_CREDENTIALS` |
| POST | `/auth/logout` | – | `204` (adds the token's jti to the denylist) | `401` |
| GET | `/auth/me` | – | `200` current user | `401` |
| GET | `/health` | – | `200 {"status":"ok"}` | – |

### 5.2 Business endpoints (12)

| # | Method | Path | Role | Purpose |
|---|---|---|---|---|
| 1 | POST | `/products` | merchant | Create a product |
| 2 | GET | `/products` | merchant | List my products (paginated) |
| 3 | POST | `/transactions` | merchant | Start a checkout for a consumer |
| 4 | GET | `/transactions` | both | List my transactions (filter/sort/paginate) |
| 5 | GET | `/transactions/{id}` | both | Transaction detail (`service_fee` only shown to the merchant) |
| 6 | GET | `/transactions/{id}/plan-options` | consumer | Compare available plans |
| 7 | POST | `/transactions/{id}/plan` | consumer | Select a plan → creates plan + schedule |
| 8 | GET | `/plans` | consumer | List my plans (filter/sort/paginate) |
| 9 | GET | `/plans/{id}` | consumer | Plan detail + full schedule + remaining balance |
| 10 | PATCH | `/plans/{id}` | consumer | Update autopay day |
| 11 | POST | `/plans/{id}/payments` | consumer | Make a payment |
| 12 | GET | `/plans/{id}/payments` | consumer | Payment history |

**Request / response examples**

`POST /transactions` (merchant): `201`
```json
// request
{ "customer_email": "alice@example.com", "product_id": 3 }
// response
{ "id": 17, "consumer_id": 2, "merchant_id": 5, "product_id": 3,
  "amount": "1000.00", "status": "pending_plan", "service_fee": null,
  "created_at": "2026-10-03T15:00:00Z" }
```
Errors: `404 CUSTOMER_NOT_FOUND`, `404 PRODUCT_NOT_FOUND` (or not this merchant's), `422 AMOUNT_OUT_OF_RANGE`, `403 FORBIDDEN_ROLE`.

`POST /products` (merchant): `201`. Request `{ "name": "Laptop", "price": "1000.00" }`, where `price` > 0 (else `422`).

`GET /transactions/17/plan-options`: `200`
```json
{ "transaction_id": 17, "amount": "1000.00", "options": [
  { "term_months": 3,  "apr": "0.0000", "monthly_payment": "333.33", "total_interest": "0.00",   "total_cost": "1000.00" },
  { "term_months": 6,  "apr": "0.1000", "monthly_payment": "171.56", "total_interest": "29.36",  "total_cost": "1029.36" },
  { "term_months": 12, "apr": "0.1500", "monthly_payment": "90.26",  "total_interest": "83.10",  "total_cost": "1083.10" },
  { "term_months": 24, "apr": "0.3000", "monthly_payment": "55.91",  "total_interest": "341.94", "total_cost": "1341.94" }
]}
```
(Values computed with the §4 rules. The last installment absorbs rounding, e.g. 3-month: 333.33, 333.33, 333.34.)

`POST /transactions/17/plan`: `201`
```json
// request
{ "term_months": 12, "autopay_day": 15 }   // autopay_day optional
// response: PlanDetail (same shape as GET /plans/{id})
```
Errors: `404` (not yours), `409 PLAN_ALREADY_SELECTED`, `422 INVALID_TERM`.

`GET /plans/9`: `200`
```json
{ "id": 9, "transaction_id": 17, "term_months": 12, "apr": "0.1500",
  "principal": "1000.00", "monthly_payment": "90.26", "total_interest": "83.10",
  "amount_paid": "90.26", "remaining_balance": "992.84", "autopay_day": 15,
  "status": "active",
  "installments": [
    { "seq": 1, "due_date": "2026-11-15", "amount_due": "90.26", "principal": "77.76",
      "interest": "12.50", "amount_paid": "90.26", "status": "paid" },
    { "seq": 2, "due_date": "2026-12-15", "amount_due": "90.26", "principal": "78.73",
      "interest": "11.53", "amount_paid": "0.00", "status": "pending" }
  ] }
```

`PATCH /plans/9`: `200` PlanDetail
```json
{ "autopay_day": 1 }
```
Errors: `422` (not 1–28), `409 PLAN_PAID_OFF`.

`POST /plans/9/payments`: `201`
```json
// request
{ "amount": "150.00" }
// response
{ "id": 31, "plan_id": 9, "amount": "150.00", "paid_at": "2026-10-03T15:10:00Z",
  "remaining_balance": "842.84", "plan_status": "active" }
```
Errors: `400 OVERPAYMENT`, `409 PLAN_PAID_OFF`, `422` (amount ≤ 0).

**List endpoints: query parameters**

| Endpoint | Filters | Sort (`sort=`) |
|---|---|---|
| `GET /transactions` | `status`, `min_amount`, `max_amount` | `created_at`, `-created_at` (default), `amount`, `-amount` |
| `GET /plans` | `status` | `created_at`, `-created_at` (default) |
| `GET /products` | `q` (name search) | `name`, `price` |

Pagination: `page` (default 1), `size` (default 20, max 100). Response envelope:
```json
{ "items": [ ... ], "total": 42, "page": 1, "size": 20 }
```

### 5.3 Status codes & error format

| Code | When |
|---|---|
| 200 / 201 / 204 | OK / created / no content |
| 400 | Business rule violation (`OVERPAYMENT`) |
| 401 | Missing, invalid, expired or revoked token |
| 403 | Wrong role for the endpoint (`FORBIDDEN_ROLE`) |
| 404 | Not found **or belongs to another user** |
| 409 | State conflict (`PLAN_ALREADY_SELECTED`, `PLAN_PAID_OFF`, `EMAIL_TAKEN`) |
| 422 | Validation (`INVALID_TERM`, `AMOUNT_OUT_OF_RANGE`, bad autopay day, bad body) |

Every error uses one shape (produced by a custom `AppError` exception plus handlers, including one that wraps FastAPI's validation errors):
```json
{ "detail": "A plan has already been selected for this transaction.", "code": "PLAN_ALREADY_SELECTED" }
```

---

## 6. Implementation

### 6.1 Tech choices
| Concern | Choice |
|---|---|
| Framework | FastAPI, Python 3.11 |
| ORM / DB | SQLAlchemy 2.0 + PostgreSQL 16 (`psycopg[binary]`) |
| Migrations | `Base.metadata.create_all` on startup (Alembic is optional; skipped for time) |
| Auth | PyJWT (HS256, 60 min, claims `sub`, `role`, `jti`, `exp`) + `bcrypt` used directly (not passlib, which breaks with bcrypt ≥ 4.1) + `python-multipart` (required by the login form) |
| Config | `pydantic-settings` reading `.env` |
| CORS | `CORSMiddleware` allowing `http://localhost:5173` (future React app) |
| Tests | `pytest` for the amortization and payment-allocation logic |

### 6.2 Project layout
```
app/
  main.py              # app, routers, CORS, exception handlers, create_all + plan offers on startup, /health
  config.py            # Settings (DATABASE_URL, JWT_SECRET, JWT_EXPIRE_MINUTES, CORS_ORIGINS)
  database.py          # engine, SessionLocal, get_db
  models.py            # SQLAlchemy models (+ remaining_balance / next_due_date properties)
  schemas/             # Pydantic request/response models (common, auth, product, transaction, plan)
  core/
    security.py        # bcrypt hash/verify, create/decode JWT
    deps.py            # get_current_user, require_role -> MerchantUser / ConsumerUser
    errors.py          # AppError + handlers -> {detail, code}; error_responses() for Swagger
    pagination.py      # page/size params + paginate()
  services/
    amortization.py    # build_schedule(principal, apr, n, start, autopay_day): pure math
    plans.py           # offers, quotes, build_plan, select_plan, change_autopay_day
    payments.py        # apply_payment(plan, amount)
  routers/
    auth.py  products.py  transactions.py  plans.py
  seed.py              # demo users/products/transactions/plans (idempotent)
tests/
  conftest.py          # in-memory SQLite + TestClient
  test_amortization.py test_payments.py test_api.py
deploy/ec2-setup.sh    # installs Docker + compose plugin on Ubuntu
postman_collection.json  # the §8 demo flow, with status-code assertions
Dockerfile  docker-compose.yml  requirements.txt  requirements-dev.txt  pytest.ini
.env.example  .gitignore  .dockerignore
```

### 6.2.1 Run locally
```bash
cp .env.example .env              # then set JWT_SECRET (see the comment in the file)
docker compose up -d --build      # Postgres + API on http://localhost:8000/docs (or your API_PORT)
docker compose exec api python -m app.seed
```

### 6.2.2 Tests (no Docker needed: uses in-memory SQLite)
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m pytest
```
They cover the amortization math (every offer × several amounts balances to the cent), payment allocation and paid-off transitions, and the full API flow from §8, including the 400/401/403/404/409/422 cases.

### 6.3 Mock data (`python -m app.seed`)
- plan_offers: 3/6/12/24 months as in §4.
- Merchant `shop@demo.com` with products: Headphones $120, Laptop $1,000, Sofa $2,400.
- Consumer `alice@demo.com` with 1 pending transaction, 1 active plan with some payments, and 1 paid-off plan.
- Consumer `bob@demo.com` (used to show the `404` on Alice's plan).
- All demo passwords: `Password123!`.
- **Idempotent:** if users already exist, the seed does nothing. Demo plans and payments are created through `select_plan` / `apply_payment`, never with hand-written numbers, so they always match the business logic.

### 6.4 Docker & EC2
`docker-compose.yml`: `db` (postgres:16, named volume, healthcheck) and `api` (built from the Dockerfile, `depends_on: db: condition: service_healthy`, port `8000:8000`, `env_file: .env`).

`.env.example`
```
POSTGRES_USER=affirm
POSTGRES_PASSWORD=affirm
POSTGRES_DB=affirm
DATABASE_URL=postgresql+psycopg://affirm:affirm@db:5432/affirm
JWT_SECRET=change-me-to-a-random-string-of-at-least-32-bytes
JWT_EXPIRE_MINUTES=60
CORS_ORIGINS=["http://localhost:5173"]
```
Postgres has no published port, so only the API container can reach it. The API runs as a non-root user in its container.

EC2 steps
1. Launch an Ubuntu t2/t3.micro. Security group: SSH 22 (my IP), TCP 8000 (0.0.0.0/0).
2. `git clone` the repo (push it to GitHub first; or `scp` the folder), then `bash deploy/ec2-setup.sh` and log out and back in.
3. `cp .env.example .env`, then set a strong `JWT_SECRET` and DB password (change it in both `POSTGRES_PASSWORD` and `DATABASE_URL`).
4. `docker compose up -d --build`, then `docker compose exec api python -m app.seed`.
5. Open `http://<EC2-public-IP>:8000/docs`.

---

## 7. Build Order (presentation: Oct 5, 2 PM ET)

1. **Skeleton:** config, DB, models, `/health`, Docker Compose running locally.
2. **Auth:** register/login/logout/me, `get_current_user`, `require_role`, error handlers.
3. **Core logic + tests:** `amortization.py`, `payments.py`, `pytest`.
4. **Endpoints:** transactions → plan-options → select plan → plans → payments → products. If time runs short, drop the products endpoints and seed products instead (that still leaves 10 business endpoints).
5. **Deploy to EC2 early** (by the end of day 1), then redeploy as features land.
6. **Seed + demo dry run** (see §8). Polish Swagger with `summary`, `description` and `responses=`.

---

## 8. Demo Script

Import [postman_collection.json](postman_collection.json) into Postman and set `baseUrl` to `http://<EC2-IP>:8000`. Each login request saves its token (shop, Alice, Bob) and IDs carry between requests, so you can run it top to bottom without re-authorizing in Swagger three times. Every request asserts its expected status code. Show Swagger `/docs` for the documentation.

1. Swagger `/docs` on EC2 → log in as `shop@demo.com` → `POST /transactions` for Alice (Laptop $1,000).
2. Log in as Alice → `GET /transactions?status=pending_plan` → `GET /transactions/{id}/plan-options` (24-month option shown since ≥ $500).
3. `POST /transactions/{id}/plan` with `term_months: 12` → show the schedule. Repeat it → **409 PLAN_ALREADY_SELECTED**.
4. `PATCH /plans/{id}` with `autopay_day: 1` → due dates shift. Try `31` → **422**.
5. `POST /plans/{id}/payments` with `150.00` → spills into installment 2. Try paying more than the balance → **400 OVERPAYMENT**. Pay the exact balance → `paid_off`. Pay again → **409**.
6. Log in as Bob → `GET /plans/{alice_plan_id}` → **404**. As Alice → `POST /products` → **403**.
7. Log out → reuse the old token → **401**.

---

## 9. Possible Extensions (out of scope)
- Payment reminders and notifications (Need 2), using installment due dates.
- Spending-power prequalification (Need 3).
- Admin role to manage `plan_offers`.
- Alembic migrations, and S3 storage for receipts.
