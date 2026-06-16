"""Photo evidence upload + listing. Photos are stored in real object storage
(S3/Supabase) via the existing image_service; only metadata lives in the DB."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.operations import PhotoEvidence
from app.services import image_service, work_order_service

logger = logging.getLogger("agave.api.photos")
router = APIRouter(prefix="/api/photos", tags=["photos"])


@router.post("/upload", status_code=201)
async def upload_photo(
    token: str = Form(...),
    file: UploadFile = File(...),
    work_order_item_id: Optional[int] = Form(None),
    gps_latitude: Optional[float] = Form(None),
    gps_longitude: Optional[float] = Form(None),
    gps_accuracy: Optional[float] = Form(None),
    gps_source: str = Form("device"),
    captured_at: Optional[str] = Form(None),
    manual_note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Worker uploads a photo from the mobile page using their work-order token."""
    wo = work_order_service.find_by_token(db, token)
    if not wo:
        raise HTTPException(403, "Invalid or expired link")

    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    ext = "png" if (file.content_type or "").endswith("png") else "jpg"
    stored = image_service.store_image_bytes(data, ext=ext)

    if not gps_latitude:
        gps_source = "unavailable"
    captured = None
    if captured_at:
        try:
            captured = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        except ValueError:
            captured = None

    photo = PhotoEvidence(
        file_url=stored.image_url, thumbnail_url=stored.thumbnail_url,
        work_order_id=wo.id, work_order_item_id=work_order_item_id,
        field_id=wo.field_id, lot_id=wo.lot_id, zone_id=wo.zone_id,
        agave_passport_id=wo.agave_passport_id,
        gps_latitude=gps_latitude, gps_longitude=gps_longitude, gps_accuracy=gps_accuracy,
        gps_source=gps_source, captured_at=captured or datetime.utcnow(),
        uploaded_by=None, manual_note=manual_note,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return {"id": photo.id, "file_url": photo.file_url, "thumbnail_url": photo.thumbnail_url,
            "gps_source": photo.gps_source}


@router.get("")
def list_photos(work_order_id: Optional[int] = None, execution_record_id: Optional[int] = None,
                lot_id: Optional[int] = None, limit: int = Query(200, le=500),
                db: Session = Depends(get_db)):
    stmt = select(PhotoEvidence)
    if work_order_id:
        stmt = stmt.where(PhotoEvidence.work_order_id == work_order_id)
    if execution_record_id:
        stmt = stmt.where(PhotoEvidence.execution_record_id == execution_record_id)
    if lot_id:
        stmt = stmt.where(PhotoEvidence.lot_id == lot_id)
    rows = db.execute(stmt.order_by(PhotoEvidence.uploaded_at.desc()).limit(limit)).scalars().all()
    return [
        {"id": p.id, "file_url": p.file_url, "thumbnail_url": p.thumbnail_url,
         "work_order_id": p.work_order_id, "execution_record_id": p.execution_record_id,
         "gps_latitude": p.gps_latitude, "gps_longitude": p.gps_longitude,
         "gps_source": p.gps_source, "captured_at": p.captured_at, "manual_note": p.manual_note}
        for p in rows
    ]
