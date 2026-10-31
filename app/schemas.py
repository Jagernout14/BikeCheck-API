"""Request and response models (what the iOS app sends and receives)."""

from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

Category = Literal[
    "frame", "fork", "rims", "hubs", "drivetrain",
    "headset", "cockpit", "brakes", "suspension", "other",
]

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# ---------- Auth ----------

class Credentials(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Shared catalog ----------

class CatalogCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    brand: str | None = Field(default=None, max_length=100)
    category: Category
    weight_g: int | None = Field(default=None, ge=0, le=100_000)
    needs_service: bool = True


class CatalogUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    brand: str | None = Field(default=None, max_length=100)
    category: Category | None = None
    weight_g: int | None = Field(default=None, ge=0, le=100_000)
    needs_service: bool | None = None


class CatalogOut(BaseModel):
    id: int
    name: str
    brand: str | None
    category: Category
    weight_g: int | None
    needs_service: bool
    author_id: int | None
    is_mine: bool  # true -> the app can show Edit / Delete
    created_at: datetime


# ---------- Bikes ----------

class BikeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    photo_url: str | None = Field(default=None, max_length=2048)


class BikeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    photo_url: str | None = Field(default=None, max_length=2048)


class BikeOut(BaseModel):
    id: int
    name: str
    photo_url: str | None
    component_count: int
    total_weight_g: int  # sum of known component weights
    created_at: datetime


# ---------- Installed components ----------

class ComponentCreate(BaseModel):
    catalog_id: int
    installed_at: date
    note: str | None = Field(default=None, max_length=500)


class ComponentUpdate(BaseModel):
    installed_at: date | None = None
    note: str | None = Field(default=None, max_length=500)


class ComponentOut(BaseModel):
    id: int
    bike_id: int
    installed_at: date
    note: str | None
    last_service_at: date | None
    last_service_mileage_km: int | None
    catalog: CatalogOut


class BikeDetailOut(BikeOut):
    components: list[ComponentOut]


# ---------- Service records ----------

class ServiceCreate(BaseModel):
    done_at: date
    mileage_km: int = Field(ge=0, le=1_000_000)
    note: str | None = Field(default=None, max_length=500)


class ServiceUpdate(BaseModel):
    done_at: date | None = None
    mileage_km: int | None = Field(default=None, ge=0, le=1_000_000)
    note: str | None = Field(default=None, max_length=500)


class ServiceOut(BaseModel):
    id: int
    component_id: int
    done_at: date
    mileage_km: int
    note: str | None
    created_at: datetime


class ServiceHistoryOut(ServiceOut):
    """A service record with context, for the History tab."""
    component_name: str
    component_category: Category
    bike_id: int
    bike_name: str
