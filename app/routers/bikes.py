"""Private bikes and the components installed on them."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..db import get_db, utc_now
from ..deps import (COMPONENT_SELECT, component_to_dict, get_current_user,
                    get_owned_component, not_found)
from ..schemas import (BikeCreate, BikeDetailOut, BikeOut, BikeUpdate,
                       ComponentCreate, ComponentOut)

router = APIRouter(prefix="/bikes", tags=["bikes"])

BIKE_SELECT = """
SELECT b.id, b.name, b.photo_url, b.created_at,
       COUNT(bc.id) AS component_count,
       COALESCE(SUM(c.weight_g), 0) AS total_weight_g
FROM bikes b
LEFT JOIN bike_components bc ON bc.bike_id = b.id
LEFT JOIN catalog_components c ON c.id = bc.catalog_id
WHERE b.owner_id = ?
"""


def _get_bike(db: sqlite3.Connection, bike_id: int, user_id: int) -> dict:
    row = db.execute(BIKE_SELECT + " AND b.id = ? GROUP BY b.id", (user_id, bike_id)).fetchone()
    if row is None:
        raise not_found("Bike")
    return dict(row)


@router.get("", response_model=list[BikeOut])
def list_bikes(user: sqlite3.Row = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(BIKE_SELECT + " GROUP BY b.id ORDER BY b.created_at, b.id", (user["id"],))
    return [dict(r) for r in rows]


@router.post("", response_model=BikeOut, status_code=status.HTTP_201_CREATED)
def create_bike(
    body: BikeCreate,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute(
        "INSERT INTO bikes (owner_id, name, photo_url, created_at) VALUES (?, ?, ?, ?)",
        (user["id"], body.name, body.photo_url, utc_now()),
    )
    db.commit()
    return _get_bike(db, cur.lastrowid, user["id"])


@router.get("/{bike_id}", response_model=BikeDetailOut)
def get_bike(
    bike_id: int,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    bike = _get_bike(db, bike_id, user["id"])
    bike["components"] = _list_components(db, bike_id, user["id"])
    return bike


@router.patch("/{bike_id}", response_model=BikeOut)
def update_bike(
    bike_id: int,
    body: BikeUpdate,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _get_bike(db, bike_id, user["id"])
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise HTTPException(422, "name cannot be null")
    if changes:
        sets = ", ".join(f"{k} = ?" for k in changes)
        db.execute(f"UPDATE bikes SET {sets} WHERE id = ?", [*changes.values(), bike_id])
        db.commit()
    return _get_bike(db, bike_id, user["id"])


@router.delete("/{bike_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bike(
    bike_id: int,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _get_bike(db, bike_id, user["id"])
    db.execute("DELETE FROM bikes WHERE id = ?", (bike_id,))  # components & services cascade
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Components on a bike ----------

def _list_components(db: sqlite3.Connection, bike_id: int, user_id: int) -> list[dict]:
    rows = db.execute(
        COMPONENT_SELECT + " AND bc.bike_id = ? ORDER BY c.category, c.name", (user_id, bike_id)
    ).fetchall()
    return [component_to_dict(r, user_id) for r in rows]


@router.get("/{bike_id}/components", response_model=list[ComponentOut])
def list_bike_components(
    bike_id: int,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _get_bike(db, bike_id, user["id"])
    return _list_components(db, bike_id, user["id"])


@router.post("/{bike_id}/components", response_model=ComponentOut, status_code=status.HTTP_201_CREATED)
def install_component(
    bike_id: int,
    body: ComponentCreate,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _get_bike(db, bike_id, user["id"])
    exists = db.execute("SELECT 1 FROM catalog_components WHERE id = ?", (body.catalog_id,)).fetchone()
    if exists is None:
        raise not_found("Catalog component")
    cur = db.execute(
        "INSERT INTO bike_components (bike_id, catalog_id, installed_at, note) VALUES (?, ?, ?, ?)",
        (bike_id, body.catalog_id, body.installed_at.isoformat(), body.note),
    )
    db.commit()
    return get_owned_component(db, cur.lastrowid, user["id"])
