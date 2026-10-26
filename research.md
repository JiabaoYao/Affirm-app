## Users
1. Users for all business (Buiness insight)
```
1. Consumers (shoppers / borrowers)
2. Merchants (sellers)
3. Platform and wallet partners
4. Internal operators
5. Funding and bank partners
```


2. Users for core business (This project)
   | Who | Role in the installment business |
   |---|---|
   | **Borrower (consumer)** | Applies, sees plan offers, picks a term, signs the loan agreement, repays, asks for refunds, gets hardship help or goes delinquent. |
   | **Merchant** | Starts the financed checkout, gets paid upfront in full minus a fee, funds 0% APR promos, and triggers refunds and cancellations that change the loan balance. Inside a merchant there are often separate roles: owner/admin, store staff, finance. |
   | **Risk / underwriting analyst** (internal) | Sets approval rules, credit limits, and which terms and APRs each risk tier gets. Reviews edge cases and fraud flags. |
   | **Servicing / support agent** (internal) | Answers borrower questions, changes payment dates or methods, applies hardship plans, fixes misapplied payments. |
   | **Collections agent** (internal) | Works overdue accounts: reminders, payment arrangements, and eventually charge-off or handoff to an outside agency. |
   | **Finance / accounting** (internal) | Reconciles money in and out: merchant settlements, borrower repayments, refunds, interest income, losses. |
   | **Compliance** (internal) | Makes sure disclosures (APR, total cost, schedule), adverse-action notices, and state rules are followed. |


## Roles and Responsiblity
1. Who generate and control the offers?
* Program / PlanTemplate (created by admin, attached to a merchant): allowed terms, APR range or fixed APR, who pays for 0% promos, and order amount limits.
* Upfront (merchant involved): The merchant and Affirm agree on which plan types can appear at their checkout, such as Pay in 4, 6- or 12-month plans, and any 0% promos the merchant is willing to pay for, plus limits like minimum and maximum order size. The merchant can change this setup later.
* At checkout (merchant not involved): When a customer applies, Affirm’s system decides on its own what this person gets: approved or not, which of the allowed plans, what APR, and what amount. The merchant doesn’t see or approve that offer. It just gets back “approved” or “declined” and, if approved, the order.

2. What customers can do?
* Choose Affirm as the payment method at the merchant's checkout (paying in full is handled by the merchant, outside Affirm).
* Apply and check eligibility (soft credit check) (Always awailable and show credit score in this project).
* See plan offers and pick a term.
* Review and accept the loan agreement (APR, total cost, payment schedule, down payment if any).
* Add and manage payment methods (bank account or debit card) and turn autopay on or off.
* Make payments: scheduled installments, extra payments, or pay off the loan early with no fee.
* See loan details: purchase info, installment schedule, remaining balance, and payment history.
* See balance updates after a merchant refund, or open a dispute (e.g., item not received).
* Receive notifications: autopay confirmations, upcoming due dates, and overdue reminders.
* Contact support or request hardship help if they can't make a payment. (ignore in this project)


3. What merchants can do?
* Apply to become an Affirm merchant.
* Integrate Affirm into checkout (API/SDK) and get API keys and webhooks.
* Configure which financing programs to offer: plan types, terms, order min/max, and merchant-funded 0% APR promos.
* Show promotional messaging on product and cart pages (e.g., "as low as $X/month").
* Offer Affirm in physical stores (e.g., customer applies via a link or QR code). (ignore in this project)
* Create checkouts and receive the result: approved, declined, or cancelled by the customer.
* Manage orders after approval: capture when the order ships, void an authorization, or update order info (shipping address, tracking).
* Issue full or partial refunds (which reduce the customer's loan balance). (ignore in this project)
* Respond to disputes an
  fraud notices by submitting evidence (e.g., proof of delivery) within the required time. (ignore in this project)
* View transactions, fees, settlements/payouts, and reconciliation reports.
* Manage team members and their roles (owner/admin, store staff, finance). (ignore in this project)
* Contact merchant support. (ignore in this project)


4. What internal operators can do?

**Risk / underwriting**
* Define approval rules and risk tiers (e.g., credit score bands, max loan amount per tier).
* Configure which terms and APRs each risk tier can be offered.
* Review applications flagged for manual review (edge cases, possible fraud) and approve or decline.
* Monitor loan performance (approval rate, delinquency rate, losses) and adjust rules.

**Merchant operations / merchant risk**
* Review and approve new merchant applications (business verification, merchant risk check).
* Set up a merchant's programs: allowed plans, terms, order limits, fee rates, 0% promos.
* Monitor merchants for fraud, high refund or dispute rates; hold payouts or suspend a merchant if needed.

**Servicing / customer support**
* Look up a customer's account, loans, schedule, and payment history.
* Change a payment date or payment method on the customer's request.
* Fix payment problems (e.g., a payment applied to the wrong loan, a failed autopay).
* Apply hardship options (e.g., temporary reduced payments or a payment plan change).
* Handle disputes between customers and merchants and decide outcomes based on evidence.

**Collections**
* See overdue loans grouped by how late they are (e.g., 1–30, 31–60, 60+ days).
* Send reminders and contact customers about overdue payments.
* Set up payment arrangements for customers who are behind.
* Mark loans as charged off, or hand them to an outside collection agency.

**Finance / accounting**
* Reconcile money: merchant payouts, customer repayments, refunds, fees, interest income.
* Review and resolve mismatches (e.g., payment received but not matched to a loan).
* Track credit losses from charged-off loans.

**Compliance**
* Manage required disclosures and loan agreement templates.
* Review adverse-action notices (reasons sent to customers who were declined).
* Audit actions taken by other operators.

**System admin**
* Create internal accounts and assign roles and permissions.
* View the audit log of who changed what and when.


## Roles and Pages
| | Customer | Merchant | Internal operator |
|---|---|---|---|
| **Where** | Consumer app / website | Merchant dashboard (a separate business portal) | Internal admin console, not public |
| **Register** | Self sign-up, usually phone number or email plus a verification code | Business applies to become a merchant. After approval, the owner **invites** team members | **No public registration.** Accounts are created by an admin, usually through the company's single sign-on (SSO) |
| **Login** | Phone/email plus a one-time code or password | Email plus password, often with 2FA | Company SSO plus 2FA, often only from a company device or network |
| **Home page** | My loans, upcoming payments, offers | Orders, settlements and payouts, disputes | Depends on role: review queue, overdue loans, merchant list, audit log |
| **Logout** | Yes | Yes | Yes, with shorter session timeouts |