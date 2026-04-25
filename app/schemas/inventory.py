"""app/schemas/inventory.py — Inventory item and stock movement schemas."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from app.core.constants import InventoryItemType, InventoryStatus, MovementType
from app.schemas.common import HopeAidBase


class InventoryItemCreate(HopeAidBase):
    item_name: str = Field(..., min_length=1, max_length=255)
    item_type: InventoryItemType
    quantity: float = Field(..., ge=0)
    unit: Optional[str] = Field(None, max_length=50)
    location_name: Optional[str] = None
    expiry_date: Optional[date] = None
    minimum_threshold: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None


class InventoryItemUpdate(HopeAidBase):
    item_name: Optional[str] = None
    item_type: Optional[InventoryItemType] = None
    unit: Optional[str] = None
    location_name: Optional[str] = None
    expiry_date: Optional[date] = None
    minimum_threshold: Optional[float] = None
    notes: Optional[str] = None


class InventoryAdjustRequest(HopeAidBase):
    quantity_change: float  # positive = add, negative = remove
    movement_type: MovementType
    reason: Optional[str] = None
    reference_case_id: Optional[UUID] = None


class InventoryDistributeRequest(HopeAidBase):
    """Distribute resources to a case — validates sufficient stock."""
    item_id: UUID
    quantity: float = Field(..., gt=0)
    reference_case_id: UUID
    reason: Optional[str] = None


class InventoryItemOut(HopeAidBase):
    id: UUID
    organization_id: UUID
    item_name: str
    item_type: InventoryItemType
    quantity: float
    unit: Optional[str]
    location_name: Optional[str]
    expiry_date: Optional[date]
    status: InventoryStatus
    minimum_threshold: Optional[float]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class StockMovementOut(HopeAidBase):
    id: UUID
    item_id: UUID
    quantity_change: float
    movement_type: MovementType
    reason: Optional[str]
    reference_case_id: Optional[UUID]
    created_by_user_id: Optional[UUID]
    created_at: datetime
