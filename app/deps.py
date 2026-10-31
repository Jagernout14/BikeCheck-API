"""Shared dependencies and helpers used by the routers."""

from typing import Optional
import sqlite3

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import get_db
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: sqlite3.Connection = Depends(get_db),
) -> sqlite3.Row:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        raise unauthorized
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise unauthorized
    return user


def not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


def catalog_to_dict(row: sqlite3.Row, user_id: int, prefix: str = "") -> dict:
    """Builds CatalogOut data from a row; `prefix` handles joined column aliases."""
    author_id = row[f"{prefix}author_id"]
    return {
        "id": row[f"{prefix}id"],
        "name": row[f"{prefix}name"],
        "brand": row[f"{prefix}brand"],
        "category": row[f"{prefix}category"],
        "weight_g": row[f"{prefix}weight_g"],
        "needs_service": bool(row[f"{prefix}needs_service"]),
        "author_id": author_id,
        "is_mine": author_id is not None and author_id == user_id,
        "created_at": row[f"{prefix}created_at"],
    }


# Installed components joined with their catalog item and latest service.
COMPONENT_SELECT = """
SELECT bc.id, bc.bike_id, bc.installed_at, bc.note,
       c.id AS c_id, c.name AS c_name, c.brand AS c_brand, c.category AS c_category,
       c.weight_g AS c_weight_g, c.needs_service AS c_needs_service,
       c.author_id AS c_author_id, c.created_at AS c_created_at,
       (SELECT s.done_at FROM services s WHERE s.component_id = bc.id
        ORDER BY s.done_at DESC, s.id DESC LIMIT 1) AS last_service_at,
       (SELECT s.mileage_km FROM services s WHERE s.component_id = bc.id
        ORDER BY s.done_at DESC, s.id DESC LIMIT 1) AS last_service_mileage_km
FROM bike_components bc
JOIN bikes b ON b.id = bc.bike_id
JOIN catalog_components c ON c.id = bc.catalog_id
WHERE b.owner_id = ?
"""


def component_to_dict(row: sqlite3.Row, user_id: int) -> dict:
    return {
        "id": row["id"],
        "bike_id": row["bike_id"],
        "installed_at": row["installed_at"],
        "note": row["note"],
        "last_service_at": row["last_service_at"],
        "last_service_mileage_km": row["last_service_mileage_km"],
        "catalog": catalog_to_dict(row, user_id, prefix="c_"),
    }


def get_owned_component(db: sqlite3.Connection, component_id: int, user_id: int) -> dict:
    row = db.execute(COMPONENT_SELECT + " AND bc.id = ?", (user_id, component_id)).fetchone()
    if row is None:
        raise not_found("Component")
    return component_to_dict(row, user_id)
