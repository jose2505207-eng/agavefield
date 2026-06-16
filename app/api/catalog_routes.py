"""Product & Activity catalog API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.ops_schemas import (
    ActivityCreate,
    ActivityRead,
    ActivityUpdate,
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from app.services import catalog_service

router = APIRouter(prefix="/api", tags=["catalogs"])


# --- Products ---
@router.get("/products", response_model=list[ProductRead])
def list_products(include_inactive: bool = True, db: Session = Depends(get_db)):
    return catalog_service.list_products(db, include_inactive=include_inactive)


@router.post("/products", response_model=ProductRead, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    obj = catalog_service.create_product(db, payload.model_dump(exclude_none=True))
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/products/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)):
    obj = catalog_service.update_product(db, product_id, payload.model_dump(exclude_none=True))
    if not obj:
        raise HTTPException(404, "Product not found")
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    result = catalog_service.delete_or_deactivate_product(db, product_id)
    if result == "not_found":
        raise HTTPException(404, "Product not found")
    db.commit()
    return {"result": result}


# --- Activities ---
@router.get("/activities", response_model=list[ActivityRead])
def list_activities(include_inactive: bool = True, db: Session = Depends(get_db)):
    return catalog_service.list_activities(db, include_inactive=include_inactive)


@router.post("/activities", response_model=ActivityRead, status_code=201)
def create_activity(payload: ActivityCreate, db: Session = Depends(get_db)):
    obj = catalog_service.create_activity(db, payload.model_dump(exclude_none=True))
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/activities/{activity_id}", response_model=ActivityRead)
def update_activity(activity_id: int, payload: ActivityUpdate, db: Session = Depends(get_db)):
    obj = catalog_service.update_activity(db, activity_id, payload.model_dump(exclude_none=True))
    if not obj:
        raise HTTPException(404, "Activity not found")
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/activities/{activity_id}")
def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    result = catalog_service.delete_or_deactivate_activity(db, activity_id)
    if result == "not_found":
        raise HTTPException(404, "Activity not found")
    db.commit()
    return {"result": result}
