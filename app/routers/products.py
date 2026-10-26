from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import ActiveMerchant, DbSession
from app.core.errors import AppError, error_responses
from app.core.pagination import Pagination, paginate
from app.models import Product, utcnow
from app.schemas.common import Page
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate

router = APIRouter(prefix="/products", tags=["Products"])

_SORT_COLUMNS = {"name": Product.name, "price": Product.price, "created_at": Product.created_at}


@router.post(
    "",
    status_code=201,
    response_model=ProductOut,
    summary="Create a product (merchant)",
    responses=error_responses(401, 403, 422),
)
def create_product(body: ProductCreate, merchant: ActiveMerchant, db: DbSession) -> Product:
    product = Product(merchant_id=merchant.id, name=body.name.strip(), price=body.price, created_at=utcnow())
    db.add(product)
    db.commit()
    return product


@router.get(
    "",
    response_model=Page[ProductOut],
    summary="List my products (merchant)",
    responses=error_responses(401, 403, 422),
)
def list_products(
    merchant: ActiveMerchant,
    db: DbSession,
    pagination: Pagination,
    q: Annotated[str | None, Query(max_length=100, description="Case-insensitive name search")] = None,
    sort: Literal["name", "-name", "price", "-price", "created_at", "-created_at"] = "name",
) -> Page[ProductOut]:
    stmt = select(Product).where(Product.merchant_id == merchant.id)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    column = _SORT_COLUMNS[sort.lstrip("-")]
    stmt = stmt.order_by(column.desc() if sort.startswith("-") else column.asc(), Product.id)
    items, total = paginate(db, stmt, pagination)
    return Page[ProductOut](
        items=[ProductOut.model_validate(p) for p in items], total=total, page=pagination.page, size=pagination.size
    )


@router.patch(
    "/{product_id}",
    response_model=ProductOut,
    summary="Rename or reprice a product (merchant)",
    description="Existing orders keep the price they were made at.",
    responses=error_responses(401, 403, 404, 422),
)
def update_product(product_id: int, body: ProductUpdate, merchant: ActiveMerchant, db: DbSession) -> Product:
    product = db.scalar(select(Product).where(Product.id == product_id, Product.merchant_id == merchant.id))
    if product is None:
        raise AppError(404, "PRODUCT_NOT_FOUND", "Product not found.")
    if body.name is not None:
        product.name = body.name.strip()
    if body.price is not None:
        product.price = body.price
    db.commit()
    return product
