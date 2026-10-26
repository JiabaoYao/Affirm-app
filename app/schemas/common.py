from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

# Money in requests: positive, at most 2 decimal places. Serialized as a string ("150.00") so no float rounding.
MoneyIn = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


# built from an object with attributes, which in practice means a SQLAlchemy model instance like User
class ORMModel(BaseModel):
    # from_attributes=True lets Pydantic read obj.id, obj.email and so on. Without it, Pydantic only accepts dicts (or an instance of the model itself).
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
