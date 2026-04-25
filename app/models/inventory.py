"""app/models/inventory.py — InventoryItem and StockMovement models."""

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import InventoryItemType, InventoryStatus, MovementType
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    pass


class InventoryItem(UUIDMixin, TimestampMixin, Base):
    """
    A trackable resource item owned by an organization.
    Status auto-managed based on quantity vs minimum_threshold.
    """

    __tablename__ = "inventory_items"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    item_type: Mapped[InventoryItemType] = mapped_column(
        SAEnum(InventoryItemType, name="inventory_item_type_enum"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # kg, liters, units
    location_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[InventoryStatus] = mapped_column(
        SAEnum(InventoryStatus, name="inventory_status_enum"),
        default=InventoryStatus.available,
        nullable=False,
        index=True,
    )
    minimum_threshold: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2), nullable=True, default=0
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ─── Relationships ───────────────────────────────────────────────────────
    movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement", back_populates="item", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<InventoryItem id={self.id} name={self.item_name} qty={self.quantity}>"


class StockMovement(UUIDMixin, Base):
    """
    Immutable ledger of quantity changes on an inventory item.
    quantity_change: positive = stock in, negative = stock out.
    """

    __tablename__ = "stock_movements"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity_change: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    movement_type: Mapped[MovementType] = mapped_column(
        SAEnum(MovementType, name="movement_type_enum"), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # ─── Relationships ───────────────────────────────────────────────────────
    item: Mapped["InventoryItem"] = relationship("InventoryItem", back_populates="movements")
