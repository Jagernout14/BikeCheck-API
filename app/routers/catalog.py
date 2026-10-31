"""Shared component catalog: everyone can read and add; only the author edits/deletes."""

from typing import Optional
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ..db import get_db, utc_now
from ..deps import catalog_to_dict, get_current_user, not_found
from ..schemas import CatalogCreate, CatalogOut, CatalogUpdate, Category, Page

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _get_row(db: sqlite3.Connection, item_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM catalog_components WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise not_found("Catalog component")
    return row


def _require_author(row: sqlite3.Row, user_id: int) -> None:
    if row["author_id"] is None or row["author_id"] != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author can change this component")


@router.get("", response_model=Page[CatalogOut])
def list_catalog(
    q: Optional[str] = Query(default=None, max_length=100, description="Search in name and brand"),
    category: Optional[Category] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    where, params = [], []
    if q:
        where.append("(name LIKE ? OR brand LIKE ?)")
        params += [f"%{q.strip()}%"] * 2
    if category:
        where.append("category = ?")
        params.append(category)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total = db.execute(f"SELECT COUNT(*) FROM catalog_components {where_sql}", params).fetchone()[0]
    rows = db.execute(
        f"SELECT * FROM catalog_components {where_sql} "
        "ORDER BY category, name COLLATE NOCASE LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return {
        "items": [catalog_to_dict(r, user["id"]) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


@router.post("", response_model=CatalogOut, status_code=status.HTTP_201_CREATED)
def create_catalog_item(
    body: CatalogCreate,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute(
        "INSERT INTO catalog_components "
        "(name, brand, category, weight_g, needs_service, author_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (body.name, body.brand, body.category, body.weight_g,
         int(body.needs_service), user["id"], utc_now()),
    )
    db.commit()
    return catalog_to_dict(_get_row(db, cur.lastrowid), user["id"])


@router.get("/{item_id}", response_model=CatalogOut)
def get_catalog_item(
    item_id: int,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    return catalog_to_dict(_get_row(db, item_id), user["id"])


@router.patch("/{item_id}", response_model=CatalogOut)
def update_catalog_item(
    item_id: int,
    body: CatalogUpdate,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    row = _get_row(db, item_id)
    _require_author(row, user["id"])
    changes = body.model_dump(exclude_unset=True)
    if "needs_service" in changes and changes["needs_service"] is not None:
        changes["needs_service"] = int(changes["needs_service"])
    for required in ("name", "category", "needs_service"):
        if required in changes and changes[required] is None:
            raise HTTPException(422, f"{required} cannot be null")
    if changes:
        sets = ", ".join(f"{k} = ?" for k in changes)
        db.execute(f"UPDATE catalog_components SET {sets} WHERE id = ?", [*changes.values(), item_id])
        db.commit()
    return catalog_to_dict(_get_row(db, item_id), user["id"])


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_catalog_item(
    item_id: int,
    user: sqlite3.Row = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    row = _get_row(db, item_id)
    _require_author(row, user["id"])
    in_use = db.execute(
        "SELECT COUNT(*) FROM bike_components WHERE catalog_id = ?", (item_id,)
    ).fetchone()[0]
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Component is installed on {in_use} bike(s) and cannot be deleted",
        )
    db.execute("DELETE FROM catalog_components WHERE id = ?", (item_id,))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
