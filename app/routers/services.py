"""All of the user's service records (History tab) and editing single records."""

from typing import Optional
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ..db import get_db
from ..deps import get_current_user, not_found
from ..schemas import Page, ServiceHistoryOut, ServiceOut, ServiceUpdate

router = APIRouter(prefix="/services", tags=["services"])

HISTORY_FROM = """
FROM services s
JOIN bike_components bc ON bc.id = s.component_id
JOIN bikes b ON b.id = bc.bike_id
JOIN catalog_components c ON c.id = bc.catalog_id
WHERE b.owner_id = ?
"""


def _get_owned_service(db: sqlite3.Connection, service_id: int, user_id: int) -> dict:
    row = db.execute("SELECT s.* " + HISTORY_FROM + " AND s.id = ?", (user_id, service_id)).fetchone()
    if row is None:
        raise not_found("Service record")
    return dict(row)


@router.get("", response_model=Page[ServiceHistoryOut])
def list_services(
    bike_id: Optional[int] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    params: list = [user["id"]]
    extra = ""
    if bike_id is not None:
        owns = db.execute(
            "SELECT 1 FROM bikes WHERE id = ? AND owner_id = ?", (bike_id, user["id"])
        ).fetchone()
        if owns is None:
            raise not_found("Bike")
        extra = " AND b.id = ?"
        params.append(bike_id)

    total = db.execute("SELECT COUNT(*) " + HISTORY_FROM + extra, params).fetchone()[0]
    rows = db.execute(
        "SELECT s.*, c.name AS component_name, c.category AS component_category, "
        "b.id AS bike_id, b.name AS bike_name "
        + HISTORY_FROM + extra
        + " ORDER BY s.done_at DESC, s.id DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return {"items": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/{service_id}", response_model=ServiceOut)
def get_service(
    service_id: int,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    return _get_owned_service(db, service_id, user["id"])


@router.patch("/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: int,
    body: ServiceUpdate,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _get_owned_service(db, service_id, user["id"])
    changes = body.model_dump(exclude_unset=True)
    for required in ("done_at", "mileage_km"):
        if required in changes and changes[required] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{required} cannot be null")
    if "done_at" in changes:
        changes["done_at"] = changes["done_at"].isoformat()
    if changes:
        sets = ", ".join(f"{k} = ?" for k in changes)
        db.execute(f"UPDATE services SET {sets} WHERE id = ?", [*changes.values(), service_id])
        db.commit()
    return _get_owned_service(db, service_id, user["id"])


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(
    service_id: int,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _get_owned_service(db, service_id, user["id"])
    db.execute("DELETE FROM services WHERE id = ?", (service_id,))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
