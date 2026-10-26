// Mirrors the FastAPI Pydantic schemas. Money and rates arrive as strings ("150.00", "0.1000").

export type Money = string;
export type Role = "consumer" | "merchant" | "admin";
export type MerchantStatus = "pending" | "active" | "suspended";
export type TransactionStatus =
  | "in_review"
  | "approved"
  | "declined"
  | "cancelled"
  | "authorized"
  | "captured"
  | "voided";
export type PlanStatus = "pending_capture" | "active" | "paid_off" | "voided";
export type InstallmentStatus = "pending" | "partial" | "paid";
export type TierDecision = "approve" | "review" | "decline";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface ApiErrorBody {
  detail: string;
  code: string;
  errors?: { field: string; message: string }[];
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  merchant_status: MerchantStatus | null;
  business_name: string | null;
  created_at: string;
}

export interface TokenOut {
  access_token: string;
  token_type: string;
  expires_in: number;
  role: Role;
}

export interface RegisterIn {
  email: string;
  password: string;
  full_name: string;
  role: "consumer" | "merchant";
  business_name?: string;
}

export interface StoreProduct {
  id: number;
  merchant_id: number;
  merchant_name: string;
  name: string;
  price: Money;
  created_at: string;
  as_low_as_monthly: Money | null;
  as_low_as_term: number | null;
  has_zero_apr: boolean;
}

export interface StoreMerchant {
  id: number;
  business_name: string;
  product_count: number;
  terms: number[];
  has_zero_apr: boolean;
}

export interface Credit {
  score: number;
  risk_tier: string;
  decision: TierDecision;
  apr: string;
  max_amount: Money;
  max_term_months: number;
  outstanding_balance: Money;
  spending_power: Money;
  checked_at: string;
}

export interface Transaction {
  id: number;
  consumer_id: number;
  customer_email: string;
  customer_name: string;
  merchant_id: number;
  merchant_name: string;
  product_id: number;
  product_name: string;
  amount: Money;
  status: TransactionStatus;
  decision_reason: string | null;
  credit_score: number | null;
  risk_tier: string | null;
  merchant_fee: Money | null;
  tracking_number: string | null;
  plan_id: number | null;
  created_at: string;
  decided_at: string | null;
  captured_at: string | null;
  voided_at: string | null;
}

export interface PlanOption {
  term_months: number;
  apr: string;
  zero_apr_promo: boolean;
  monthly_payment: Money;
  total_interest: Money;
  total_cost: Money;
}

export interface PlanOptions {
  transaction_id: number;
  amount: Money;
  credit_score: number;
  risk_tier: string;
  options: PlanOption[];
}

export interface SelectPlanIn {
  term_months: number;
  autopay_day?: number;
  autopay_enabled: boolean;
  payment_method_id?: number;
  agree: boolean;
}

export interface Installment {
  seq: number;
  due_date: string;
  amount_due: Money;
  principal: Money;
  interest: Money;
  amount_paid: Money;
  status: InstallmentStatus;
  days_past_due: number;
}

export interface PlanSummary {
  id: number;
  transaction_id: number;
  product_name: string;
  merchant_name: string;
  term_months: number;
  apr: string;
  zero_apr_promo: boolean;
  principal: Money;
  monthly_payment: Money;
  total_interest: Money;
  amount_paid: Money;
  remaining_balance: Money;
  autopay_day: number;
  autopay_enabled: boolean;
  payment_method_id: number | null;
  next_due_date: string | null;
  days_past_due: number;
  overdue_amount: Money;
  status: PlanStatus;
  agreement_accepted_at: string | null;
  created_at: string;
  activated_at: string | null;
}

export interface PlanDetail extends PlanSummary {
  installments: Installment[];
}

export interface PlanUpdate {
  autopay_day?: number;
  autopay_enabled?: boolean;
  payment_method_id?: number;
}

export interface Payment {
  id: number;
  plan_id: number;
  amount: Money;
  payment_method_id: number | null;
  source: "manual" | "autopay";
  paid_at: string;
}

export interface PaymentResult extends Payment {
  remaining_balance: Money;
  plan_status: PlanStatus;
}

export interface PaymentMethod {
  id: number;
  kind: "bank" | "card";
  label: string;
  last4: string;
  is_default: boolean;
  created_at: string;
}

export interface PaymentMethodIn {
  kind: "bank" | "card";
  label: string;
  last4: string;
  is_default?: boolean;
}

export interface Notification {
  id: number;
  kind: string;
  title: string;
  body: string;
  link: string | null;
  read_at: string | null;
  created_at: string;
}

export interface NotificationPage extends Page<Notification> {
  unread: number;
}

export interface Product {
  id: number;
  merchant_id: number;
  name: string;
  price: Money;
  created_at: string;
}

export interface Program {
  id: number;
  term_months: number;
  zero_apr_promo: boolean;
  min_amount: Money;
  max_amount: Money;
  active: boolean;
  created_at: string;
}

export interface ProgramIn {
  term_months: number;
  zero_apr_promo: boolean;
  min_amount: string;
  max_amount: string;
  active?: boolean;
}

export interface MerchantSummary {
  business_name: string;
  fee_rate: string;
  promo_fee_rate: string;
  gross_volume: Money;
  fees: Money;
  net_payout: Money;
  awaiting_capture_amount: Money;
  counts: Record<TransactionStatus, number>;
}

export interface AdminMerchant {
  user_id: number;
  email: string;
  full_name: string;
  business_name: string;
  status: MerchantStatus;
  fee_rate: string;
  promo_fee_rate: string;
  created_at: string;
  reviewed_at: string | null;
}

export interface RiskTier {
  id: number;
  name: string;
  min_score: number;
  max_score: number;
  decision: TierDecision;
  apr: string;
  max_amount: Money;
  max_term_months: number;
}

export type DelinquencyBucket = "1-30" | "31-60" | "60+";

export interface DelinquentLoan {
  plan_id: number;
  customer_email: string;
  customer_name: string;
  merchant_name: string;
  product_name: string;
  remaining_balance: Money;
  overdue_amount: Money;
  days_past_due: number;
  bucket: DelinquencyBucket;
  next_due_date: string | null;
  autopay_enabled: boolean;
}

export interface Metrics {
  applications: number;
  approved: number;
  declined: number;
  in_review: number;
  approval_rate: string;
  active_loans: number;
  outstanding_balance: Money;
  delinquent_loans: number;
  delinquency_rate: string;
  captured_volume: Money;
  fee_revenue: Money;
  pending_merchants: number;
  statuses: Record<TransactionStatus, number>;
}

export interface RunDailyOut {
  as_of: string;
  autopay_payments: number;
  autopay_amount: Money;
  reminders: number;
  overdue_notices: number;
}

export interface AuditEntry {
  id: number;
  actor_email: string;
  action: string;
  entity: string;
  entity_id: number;
  details: Record<string, string>;
  created_at: string;
}
