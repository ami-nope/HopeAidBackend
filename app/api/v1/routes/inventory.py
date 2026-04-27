"""app/api/v1/routes/inventory.py — Inventory and stock management endpoints. All sync."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permissions
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.inventory import (
    InventoryAdjustRequest,
    InventoryDistributeRequest,
    InventoryItemCreate,
    InventoryItemOut,
    InventoryItemUpdate,
)
from app.services.inventory_service import InventoryService
from app.utils.pagination import PaginationParams, build_pagination_meta, get_pagination

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.post("/items", response_model=APIResponse[InventoryItemOut], status_code=201)
def create_item(
    data: InventoryItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("inventory:manage")),
):
    service = InventoryService(db, current_user)
    item = service.create_item(data)
    db.commit()
    db.refresh(item)
    return {"success": True, "data": InventoryItemOut.model_validate(item)}


@router.get("/items", response_model=PaginatedResponse[InventoryItemOut])
def list_items(
    pagination: PaginationParams = Depends(get_pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("inventory:view")),
):
    service = InventoryService(db, current_user)
    items, total = service.list_items(pagination.offset, pagination.page_size)
    return {
        "success": True,
        "data": [InventoryItemOut.model_validate(i) for i in items],
        "meta": build_pagination_meta(total, pagination.page, pagination.page_size),
    }


@router.put("/items/{item_id}", response_model=APIResponse[InventoryItemOut])
def update_item(
    item_id: UUID,
    data: InventoryItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("inventory:manage")),
):
    try:
        service = InventoryService(db, current_user)
        item = service.update_item(item_id, data)
        db.commit()
        db.refresh(item)
        return {"success": True, "data": InventoryItemOut.model_validate(item)}
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/items/{item_id}/adjust", response_model=APIResponse[InventoryItemOut])
def adjust_stock(
    item_id: UUID,
    request: InventoryAdjustRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("inventory:manage")),
):
    """Adjust inventory quantity. Use negative quantity_change to reduce stock."""
    try:
        service = InventoryService(db, current_user)
        item = service.adjust_stock(item_id, request)
        db.commit()
        db.refresh(item)
        return {"success": True, "data": InventoryItemOut.model_validate(item)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/distribute", response_model=APIResponse[InventoryItemOut])
def distribute_inventory(
    request: InventoryDistributeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("inventory:manage")),
):
    """Distribute inventory to a case. Validates sufficient stock exists."""
    try:
        service = InventoryService(db, current_user)
        item = service.distribute(request)
        db.commit()
        db.refresh(item)
        return {"success": True, "data": InventoryItemOut.model_validate(item)}
    except ValueError as e:
        raise HTTPException(400, str(e))
