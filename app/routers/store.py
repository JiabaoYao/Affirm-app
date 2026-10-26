from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, DbSession
from app.core.errors import error_responses
from app.core.pagination import Pagination, paginate
from app.models import MerchantProfile, MerchantStatus, Product, RiskTier, TierDecision
from app.schemas.common import Page
from app.schemas.product import StoreMerchantOut, StoreProductOut
from app.services.plans import as_low_as

router = APIRouter(prefix="/store", tags=["Store"])

_SORT_COLUMNS = {"name": Product.name, "price": Product.price}


def _best_apr(db: Session) -> Decimal | None:
    return db.scalar(select(func.min(RiskTier.apr)).where(RiskTier.decision == TierDecision.approve))


@router.get(
    "/merchants",
    response_model=list[StoreMerchantOut],
    summary="Merchants that offer Affirm",
    responses=error_responses(401),
)
def list_merchants(_: CurrentUser, db: DbSession) -> list[StoreMerchantOut]:
    counts = dict(db.execute(select(Product.merchant_id, func.count()).group_by(Product.merchant_id)).all())
    merchants = db.scalars(
        select(MerchantProfile).where(MerchantProfile.status == MerchantStatus.active)
        .order_by(MerchantProfile.business_name)
    ).unique()
    return [
        StoreMerchantOut(
            id=m.user_id,
            business_name=m.business_name,
            product_count=counts.get(m.user_id, 0),
            terms=[p.term_months for p in m.programs if p.active],
            has_zero_apr=any(p.active and p.zero_apr_promo for p in m.programs),
        )
        for m in merchants
    ]


@router.get(
    "/products",
    response_model=Page[StoreProductOut],
    summary="Browse products with \"as low as $X/mo\" messaging",
    description="Products from active merchants. The monthly figure is the lowest payment across the merchant's "
                "programs at the best risk tier's APR; the consumer's real offer depends on their credit check.",
    responses=error_responses(401, 422),
)
def list_store_products(
    _: CurrentUser,
    db: DbSession,
    pagination: Pagination,
    q: Annotated[str | None, Query(max_length=100, description="Case-insensitive name search")] = None,
    merchant_id: int | None = None,
    sort: Literal["name", "-name", "price", "-price"] = "name",
) -> Page[StoreProductOut]:
    stmt = (select(Product).join(MerchantProfile, Product.merchant_id == MerchantProfile.user_id)
            .where(MerchantProfile.status == MerchantStatus.active))
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    if merchant_id is not None:
        stmt = stmt.where(Product.merchant_id == merchant_id)
    column = _SORT_COLUMNS[sort.lstrip("-")]
    stmt = stmt.order_by(column.desc() if sort.startswith("-") else column.asc(), Product.id)
    items, total = paginate(db, stmt, pagination)

    best_apr = _best_apr(db)
    out = []
    for product in items:
        programs = product.merchant.programs
        cheapest = as_low_as(programs, best_apr, product.price) if best_apr is not None else None
        out.append(StoreProductOut(
            id=product.id,
            merchant_id=product.merchant_id,
            merchant_name=product.merchant_name,
            name=product.name,
            price=product.price,
            created_at=product.created_at,
            as_low_as_monthly=cheapest[0] if cheapest else None,
            as_low_as_term=cheapest[1] if cheapest else None,
            has_zero_apr=any(p.active and p.zero_apr_promo and p.min_amount <= product.price <= p.max_amount
                             for p in programs),
        ))
    return Page[StoreProductOut](items=out, total=total, page=pagination.page, size=pagination.size)
