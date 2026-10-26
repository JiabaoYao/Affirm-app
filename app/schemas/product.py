from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MoneyIn, ORMModel


class ProductCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "Standing Desk", "price": "650.00"}]})

    name: str = Field(min_length=1, max_length=200)
    price: MoneyIn


class ProductUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"price": "599.00"}]})

    name: str | None = Field(default=None, min_length=1, max_length=200)
    price: MoneyIn | None = None


class ProductOut(ORMModel):
    id: int
    merchant_id: int
    name: str
    price: Decimal
    created_at: datetime


class StoreProductOut(ProductOut):
    merchant_name: str
    as_low_as_monthly: Decimal | None = Field(description="Lowest monthly payment across the merchant's programs")
    as_low_as_term: int | None
    has_zero_apr: bool = Field(description="A merchant-funded 0% APR program covers this price")


class StoreMerchantOut(BaseModel):
    id: int
    business_name: str
    product_count: int
    terms: list[int]
    has_zero_apr: bool
