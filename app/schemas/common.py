"""
app/schemas/common.py — Shared Pydantic base models and response wrappers.

All API responses use the standard envelope:
  { "success": true, "data": {...}, "message": "...", "meta": {...} }
"""

from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ─── Base Config ─────────────────────────────────────────────────────────────

class HopeAidBase(BaseModel):
    """Base model with ORM mode enabled for all schemas."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ─── Pagination ──────────────────────────────────────────────────────────────

class PaginationMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int


DataT = TypeVar("DataT")


class PaginatedResponse(BaseModel, Generic[DataT]):
    success: bool = True
    data: list[DataT]
    meta: PaginationMeta


class APIResponse(BaseModel, Generic[DataT]):
    """Standard single-item API response envelope."""

    success: bool = True
    data: Optional[DataT] = None
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[Any] = None
    code: Optional[str] = None


# ─── Common Fields ────────────────────────────────────────────────────────────

class UUIDSchema(HopeAidBase):
    id: UUID


class MessageResponse(BaseModel):
    success: bool = True
    message: str
