from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class PageParams:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
        size: Annotated[int, Query(ge=1, le=100, description="Items per page (max 100)")] = 20,
    ):
        self.page = page
        self.size = size


Pagination = Annotated[PageParams, Depends()]


def paginate(db: Session, stmt: Select, params: PageParams) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = db.scalars(stmt.limit(params.size).offset((params.page - 1) * params.size)).all()
    return list(items), total or 0
