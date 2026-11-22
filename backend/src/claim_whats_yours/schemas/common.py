"""Shared response models used across endpoints."""

from pydantic import BaseModel


class Page(BaseModel):
    """One page of list results with paging metadata."""

    items: list[dict]
    page: int
    page_size: int
    total: int
