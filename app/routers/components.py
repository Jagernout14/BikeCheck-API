"""A single installed component and its service records."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..db import get_db, utc_now
from ..deps import get_current_user, get_owned_component
from ..schemas import ComponentOut, ComponentUpdate, ServiceCreate, ServiceOut

router = APIRouter(prefix="/components", tags=["components"])


@router.get("/{component_id}", response_model=ComponentOut)
def get_component(
    component_id: int,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    return get_owned_component(db, component_id, user["id"])


@router.patch("/{component_id}", response_model=ComponentOut)
def update_component(
    component_id: int,
    body: ComponentUpdate,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    get_owned_component(db, component_id, user["id"])
    changes = body.model_dump(exclude_unset=True)
    if "installed_at" in changes:
        if changes["installed_at"] is None:
            raise HTTPException(422, "installed_at cannot be null")
        changes["installed_at"] = changes["installed_at"].isoformat()
    if changes:
        sets = ", ".join(f"{k} = ?" for k in changes)
        db.execute(f"UPDATE bike_components SET {sets} WHERE id = ?", [*changes.values(), component_id])
        db.commit()
    return get_owned_component(db, component_id, user["id"])


@router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_component(
    component_id: int,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    get_owned_component(db, component_id, user["id"])
    db.execute("DELETE FROM bike_components WHERE id = ?", (component_id,))  # services cascade
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{component_id}/services", response_model=list[ServiceOut])
def list_component_services(
    component_id: int,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    get_owned_component(db, component_id, user["id"])
    rows = db.execute(
        "SELECT * FROM services WHERE component_id = ? ORDER BY done_at DESC, id DESC",
        (component_id,),
    )
    return [dict(r) for r in rows]


@router.post("/{component_id}/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def add_service(
    component_id: int,
    body: ServiceCreate,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    component = get_owned_component(db, component_id, user["id"])
    if not component["catalog"]["needs_service"]:
        raise HTTPException(422, "This component does not need service")
    cur = db.execute(
        "INSERT INTO services (component_id, done_at, mileage_km, note, created_at) VALUES (?, ?, ?, ?, ?)",
        (component_id, body.done_at.isoformat(), body.mileage_km, body.note, utc_now()),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM services WHERE id = ?", (cur.lastrowid,)).fetchone())
