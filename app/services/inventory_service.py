"""
app/services/inventory_service.py — Inventory management service.

Handles item CRUD, stock adjustments (atomic), and case distribution.
Auto-detects low stock / out of stock from quantity + threshold.

Synchronous — no async, no await.
"""

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import InventoryStatus, MovementType, UserRole
from app.core.logging import get_logger
from app.models.inventory import InventoryItem, StockMovement
from app.models.user import User
from app.schemas.inventory import (
    InventoryAdjustRequest,
    InventoryDistributeRequest,
    InventoryItemCreate,
    InventoryItemUpdate,
)
from app.services.audit_service import log_action

logger = get_logger(__name__)


def _determine_status(item: InventoryItem) -> InventoryStatus:
    """Compute the correct status based on quantity, threshold, and expiry date."""
    today = date.today()
    if item.expiry_date and item.expiry_date <= today:
        return InventoryStatus.expired
    if item.quantity <= 0:
        return InventoryStatus.out_of_stock
    if item.minimum_threshold and item.quantity <= item.minimum_threshold:
        return InventoryStatus.low_stock
    return InventoryStatus.available


class InventoryService:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user
        self.org_id = current_user.organization_id
        self.is_global_super_admin = (
            current_user.role == UserRole.super_admin and current_user.organization_id is None
        )

    def create_item(self, data: InventoryItemCreate) -> InventoryItem:
        """Create a new inventory item and record initial stock movement."""
        item = InventoryItem(
            organization_id=self.org_id,
            item_name=data.item_name,
            item_type=data.item_type,
            quantity=data.quantity,
            unit=data.unit,
            location_name=data.location_name,
            expiry_date=data.expiry_date,
            minimum_threshold=data.minimum_threshold,
            notes=data.notes,
        )
        item.status = _determine_status(item)
        self.db.add(item)
        self.db.flush()

        # Record the initial receipt as a stock movement
        if data.quantity > 0:
            movement = StockMovement(
                organization_id=self.org_id,
                item_id=item.id,
                quantity_change=data.quantity,
                movement_type=MovementType.received,
                reason="Initial stock",
                created_by_user_id=self.current_user.id,
            )
            self.db.add(movement)

        log_action(
            self.db, self.org_id, self.current_user.id,
            "INVENTORY_CREATED", "inventory_item", item.id,
            after_json={"item_name": item.item_name, "quantity": float(item.quantity)},
        )
        return item

    def get_item(self, item_id: uuid.UUID) -> Optional[InventoryItem]:
        """Fetch one item scoped to this organization."""
        query = select(InventoryItem).where(InventoryItem.id == item_id)
        if not self.is_global_super_admin:
            query = query.where(InventoryItem.organization_id == self.org_id)
        return self.db.execute(query).scalars().first()

    def list_items(self, offset: int = 0, limit: int = 20) -> tuple[list, int]:
        """List all items for this org, returns (rows, total_count)."""
        q = select(InventoryItem)
        if not self.is_global_super_admin:
            q = q.where(InventoryItem.organization_id == self.org_id)
        total = self.db.execute(select(func.count()).select_from(q.subquery())).scalar()
        items = self.db.execute(q.offset(offset).limit(limit)).scalars().all()
        return items, total

    def update_item(self, item_id: uuid.UUID, data: InventoryItemUpdate) -> InventoryItem:
        """Update item metadata (not quantity — use adjust_stock for that)."""
        item = self.get_item(item_id)
        if not item:
            raise ValueError("Item not found")

        before = {"quantity": float(item.quantity), "status": item.status.value}
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(item, field, value)
        item.status = _determine_status(item)

        log_action(
            self.db, self.org_id, self.current_user.id,
            "INVENTORY_UPDATED", "inventory_item", item.id,
            before_json=before,
        )
        return item

    def adjust_stock(self, item_id: uuid.UUID, request: InventoryAdjustRequest) -> InventoryItem:
        """
        Add or remove stock atomically.

        quantity_change: positive = receiving stock, negative = using/removing
        Raises ValueError if adjustment would result in negative stock.
        """
        item = self.get_item(item_id)
        if not item:
            raise ValueError("Item not found")

        new_qty = float(item.quantity) + request.quantity_change
        if new_qty < 0:
            raise ValueError(
                f"Adjustment would result in negative stock ({new_qty:.1f}). "
                f"Current quantity: {item.quantity}"
            )

        before_qty = float(item.quantity)
        item.quantity = new_qty
        item.status = _determine_status(item)

        movement = StockMovement(
            organization_id=self.org_id,
            item_id=item.id,
            quantity_change=request.quantity_change,
            movement_type=request.movement_type,
            reason=request.reason,
            reference_case_id=request.reference_case_id,
            created_by_user_id=self.current_user.id,
        )
        self.db.add(movement)

        log_action(
            self.db, self.org_id, self.current_user.id,
            "INVENTORY_ADJUSTED", "inventory_item", item.id,
            before_json={"quantity": before_qty},
            after_json={"quantity": new_qty, "movement_type": request.movement_type.value},
        )
        logger.info("Stock adjusted", item_id=str(item_id), change=request.quantity_change)
        return item

    def distribute(self, request: InventoryDistributeRequest) -> InventoryItem:
        """Distribute resources to a specific case — validates stock availability."""
        item = self.get_item(request.item_id)
        if not item:
            raise ValueError("Item not found")
        if item.status == InventoryStatus.out_of_stock:
            raise ValueError(f"Item '{item.item_name}' is out of stock")
        if float(item.quantity) < request.quantity:
            raise ValueError(
                f"Insufficient stock: requested {request.quantity}, available {item.quantity}"
            )

        adjust = InventoryAdjustRequest(
            quantity_change=-request.quantity,
            movement_type=MovementType.distributed,
            reason=request.reason or f"Distributed to case {request.reference_case_id}",
            reference_case_id=request.reference_case_id,
        )
        return self.adjust_stock(request.item_id, adjust)
