from __future__ import annotations

from math import ceil

from app.core.config import paging_defaults
from app.schemas.common import Pagination


def clamp_limit(limit: int | None) -> int:
    if limit is None or limit <= 0:
        return paging_defaults.limit
    return min(limit, paging_defaults.max_limit)


def build_pagination(page: int, limit: int, total: int) -> Pagination:
    page = max(page, 1)
    pages = ceil(total / limit) if limit else 0
    has_more = page < pages
    return Pagination(total=total, page=page, limit=limit, has_more=has_more)
