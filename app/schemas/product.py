from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MoneyIn, ORMModel


class ProductCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "Standing Desk", "price": "650.00"}]})

    name: str = Field(min_length=1, max_length=200)
    price: MoneyIn


class ProductOut(ORMModel):
    id: int
    merchant_id: int
    name: str
    price: Decimal
    created_at: datetime
