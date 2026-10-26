# Mini-Affirm

A small buy-now-pay-later platform modeled on affirm.com: shoppers finance purchases in fixed installments,
merchants offer Affirm at checkout, and internal operators run underwriting and servicing.

* **Backend:** Python · FastAPI · PostgreSQL · SQLAlchemy · JWT · Docker
* **Frontend:** React 18 · TypeScript · React Router · Redux Toolkit (+ RTK Query) · Tailwind · Vite
* **Deploy:** Docker Compose on AWS EC2: Nginx serves the React build and reverse-proxies `/api` to FastAPI

---

## 0. Proposal (backend phase, as submitted)
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

The frontend phase grew the scope to match the real business more closely (see `research.md`). Needs 2
(notifications) and 3 (prequalification / spending power) are now covered too.

---

## 1. Business context

Affirm sits between **shoppers** and **merchants**:

* **Merchants** decide upfront which financing programs appear at their checkout: terms, order limits,
  and any 0% APR promos they're willing to pay for. Affirm pays them the order amount minus a fee when the
  order ships.
* **At checkout, Affirm alone decides** whether a shopper is approved and on which terms, using a soft credit
  check. The merchant only learns "approved" or "declined", never the shopper's credit data.
* **Internal operators** approve merchants, tune the risk rules, review flagged applications and watch
  delinquency.

| Role | Account | Home | Can do |
|---|---|---|---|
| Shopper (`consumer`) | Self sign-up | `/app` | Check spending power, shop, check out, compare plans, sign the agreement, manage loans, payments, autopay, wallet |
| Merchant (`merchant`) | Applies, starts `pending`, an admin approves | `/merchant` | Products, financing programs (terms, 0% promos, limits), capture or void orders, tracking, payout summary |
| Affirm ops (`admin`) | Internal only (seeded; registration rejects it) | `/admin` | Approve or suspend merchants and set fees, edit risk tiers, manual-review queue, delinquency board, daily servicing job, audit log |

### Checkout flow
```
Shopper clicks "Buy with Affirm"
  └─ POST /transactions ──► soft credit check ──► risk tier ──► decision
        ├─ declined   (reason shown: score band, over spending power, no matching program)
        ├─ in_review  ──► admin approves / declines in the review queue
        └─ approved   ──► GET plan-options (merchant programs × tier APR; promos at 0%)
                             └─ POST plan {term, autopay, agree:true} ──► plan `pending_capture`, order `authorized`
Merchant ships ──► POST capture ──► plan `active` (payments open), merchant payout = amount − fee
            or ──► POST void    ──► plan `voided`, shopper owes nothing
Daily job (admin-triggered for the demo) ──► autopay charges, due-soon and overdue notifications
```

---

## 2. Data model

```
users ─┬─ merchant_profiles (status, fee_rate, promo_fee_rate) ─┬─ merchant_programs (term, 0% promo, min/max, active)
       │                                                        └─ products
       ├─ credit_checks (score) ── risk_tiers (score band, approve|review|decline, APR, limit, max term)
       ├─ payment_methods (bank|card, last4, default, soft-deleted)
       ├─ notifications (kind, link, read_at, dedupe_key)
       └─ transactions (checkout/order: status, decision_reason, merchant_fee, tracking)
              └─ plans (term, APR, autopay, status) ─┬─ installments (due date, principal, interest, paid)
                                                      └─ payments (amount, method, manual|autopay)
audit_logs (who changed what) · revoked_tokens (logout denylist)
```

* `merchant_profiles` is keyed by the owner's user id, so `merchant_id` means the same thing everywhere.
* Plans copy the term and APR at signing, so later program or tier edits never rewrite an existing loan.
* Money is `Numeric(12,2)` / `Decimal` and travels as strings (`"150.00"`), never floats.
* No Alembic: tables are created on startup. After a schema change, recreate the DB and reseed (see §5).

### Default risk tiers (editable by admins)
| Tier | Score | Decision | APR | Spending limit | Max term |
|---|---|---|---|---|---|
| A | 740–850 | approve | 10% | $15,000 | 24 mo |
| B | 680–739 | approve | 18% | $7,500 | 24 mo |
| C | 640–679 | approve | 28% | $2,500 | 12 mo |
| D | 600–639 | **review** | 30% | $1,500 | 12 mo |
| E | 300–599 | decline | — | — | — |

Spending power = tier limit − what the shopper still owes on open loans. Merchant fee = `fee_rate`, plus
`promo_fee_rate` when the shopper picked a 0% promo.

---

## 3. API (49 operations; full docs at `/api/docs`)

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register` · `POST /auth/login` · `POST /auth/logout` · `GET /auth/me` |
| Store | `GET /store/products` (search, merchant filter, sort, paging, "as low as") · `GET /store/merchants` |
| Credit | `POST /credit/check` · `GET /credit/me` |
| Transactions | `POST /transactions` (checkout + decision) · `GET /transactions` (role-scoped, filters) · `GET /transactions/{id}` · `GET …/plan-options` · `POST …/plan` · `POST …/cancel` · `POST …/capture` · `POST …/void` · `PATCH …` (tracking) |
| Plans | `GET /plans` · `GET /plans/{id}` · `PATCH /plans/{id}` (day, autopay, method) · `POST /plans/{id}/payments` · `GET /plans/{id}/payments` |
| Payment methods | `GET` · `POST` · `POST /{id}/default` · `DELETE /{id}` |
| Notifications | `GET /notifications` · `POST /{id}/read` · `POST /read-all` |
| Merchant | `GET/POST/PATCH /products` · `GET/POST/PATCH /merchant/programs` · `GET /merchant/summary` |
| Admin | `/admin/merchants` (+ approve/suspend) · `/admin/risk-tiers` · `/admin/reviews` (+ approve/decline) · `/admin/delinquency` · `/admin/metrics` · `/admin/jobs/run-daily` · `/admin/audit-log` |

Every error is `{"detail": "...", "code": "SOME_CODE"}` (plus `errors[]` for 422 validation errors).
Another user's resource returns 404, so its existence isn't revealed. The wrong role returns 403
`FORBIDDEN_ROLE`, and a pending merchant gets 403 `MERCHANT_NOT_ACTIVE`.

---

## 4. Frontend architecture (`frontend/`)

```
src/
  api/            RTK Query: baseApi (auth header, 401 → sign out) + one file of endpoints per area
  app/store.ts    configureStore: auth, checkout, toasts, api cache + error-toast listener middleware
  features/
    auth/         authSlice (token, expiry, user; persisted to localStorage) + signIn/signOut thunks
    checkout/     checkoutSlice: the multi-step wizard state (term, autopay, method, agreement)
    ui/           toastSlice: global success/error messages
  components/     Layout (role-based nav, notification bell), ProtectedRoute, ui kit, loan widgets
  pages/          public/, consumer/, merchant/, admin/
```

* **What Redux holds:** client state (session, checkout wizard, toasts) in slices, and server state in the
  RTK Query cache. Mutations invalidate tags, so a payment refetches the plan, the plan list, the credit
  card and notifications on its own.
* **Auth:** login posts the OAuth2 form, stores the JWT and loads `/auth/me`. The app signs out on its own
  when the token expires (timer) or when any call returns 401 (revoked or expired). Logout revokes the token
  server-side.
* **Protected routes:** signed out → `/login?…` (then back to the original page); wrong role → `/403`;
  unapproved merchant → "pending approval" page that unlocks itself when an admin approves.
* **Errors:** one helper turns `{detail, code, errors[]}` into messages. 422s show next to form fields;
  other failed mutations show a toast. Every list has loading, empty and error states.
* **Live-ish updates:** polling for notifications, merchant orders, the review queue and an in-review checkout.
* **Config:** `VITE_API_BASE_URL` (default `/api`). Vite's dev proxy and Nginx in prod both serve the API
  under `/api`, so the browser never makes a cross-origin call.

---

## 5. Run it

### Everything in Docker (same as EC2)
```bash
cp .env.example .env            # set JWT_SECRET and the DB password
docker compose up -d --build    # db + api + web
docker compose exec api python -m app.seed
```
Open http://localhost (the app) and http://localhost/api/docs (Swagger).
`WEB_PORT` and `API_PORT` in `.env` change the host ports.

**Upgrading from the v1 schema:** `docker compose down -v` (drops the old demo DB), then the commands above.

### Local development
```bash
# backend (needs Postgres; or run only `db` from compose)
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend && npm install
npm run dev                     # http://localhost:5173, proxies /api → API_PROXY_TARGET (default :8000)
```

### Tests
```bash
pytest -q                        # 47 tests, in-memory SQLite, no Docker
cd frontend && npm run build     # type-check + production build
```

### Demo accounts (password `Password123!`)
| Email | What it shows |
|---|---|
| `alice@demo.com` | Tier A (780). A paid-off plan, a current plan on autopay, a plan ~45 days late, an order awaiting capture |
| `bob@demo.com` | Tier C (665): fewer terms, 28% APR, $2,500 limit. Clean slate for the live checkout |
| `carol@demo.com` | Score 615: checkouts go to manual review |
| `dave@demo.com` | Score 560: declined with a reason |
| `erin@demo.com` | A 0% promo plan ~10 days late (Delinquency test) |
| `shop@demo.com`, `home@demo.com` | Active merchants (Demo Electronics, Cozy Home) |
| `newshop@demo.com` | Pending merchant application |
| `admin@demo.com` | Affirm ops console |

The login page has one-click buttons for all of these.

---

## 6. Deploy to EC2

The instance already runs Docker (see `deploy/connection.md`). In the security group, open **80** (the app).
Port 8000 is optional (direct API access).
```bash
cd ~/affirm && git pull
docker compose down -v                 # only when the schema changed: wipes demo data
docker compose up -d --build           # builds api + web (the Node build runs inside Docker)
docker compose exec api python -m app.seed
docker compose ps                      # db (healthy), api, web all Up
```
Then open `http://<public-ip>/`. Swagger is at `http://<public-ip>/api/docs`.

---

## 7. Demo script
1. **bob** → Shop → Laptop → instant decision (score 665, tier C) → 3 offers (3-mo 0% promo, 6/12 at 28%) →
   pick 12 months → add a bank account inline → sign → the loan is "awaiting shipment"; payments are blocked.
2. **shop@** → Dashboard "Ready to ship" → Capture (payout = $1,000 − $30 fee). **bob**'s bell shows "shipped",
   the plan is active → make a payment → the schedule and balance update.
3. **dave** → any purchase → declined with a reason. **carol** → in review → **admin** approves in Reviews →
   carol's checkout page unlocks on its own.
4. **newshop@** → pending page → **admin** approves with a fee rate → newshop's dashboard unlocks.
5. **admin** → Risk tiers: change tier C's APR → bob's new quotes change. Delinquency shows alice (31–60) and
   erin (1–30). Operations → run the daily job for a future date → autopay charges, overdue notices.
6. Edge cases: wrong password, `/admin` as a shopper → 403, signed-out deep link → login → back, overpayment →
   error toast, a new user's empty states, logout then the back button.
