"""Request and response models (what the iOS app sends and receives)."""

from datetime import date, datetime
from typing import Generic, Literal, TypeVar, Optional

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
    brand: Optional[str] = Field(default=None, max_length=100)
    category: Category
    weight_g: Optional[int] = Field(default=None, ge=0, le=100_000)
    needs_service: bool = True


class CatalogUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    brand: Optional[str] = Field(default=None, max_length=100)
    category: Optional[Category] = None
    weight_g: Optional[int] = Field(default=None, ge=0, le=100_000)
    needs_service: Optional[bool] = None


class CatalogOut(BaseModel):
    id: int
    name: str
    brand: Optional[str]
    category: Category
    weight_g: Optional[int]
    needs_service: bool
    author_id: Optional[int]
    is_mine: bool  # true -> the app can show Edit / Delete
    created_at: datetime


# ---------- Bikes ----------

class BikeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    photo_url: Optional[str] = Field(default=None, max_length=2048)


class BikeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    photo_url: Optional[str] = Field(default=None, max_length=2048)


class BikeOut(BaseModel):
    id: int
    name: str
    photo_url: Optional[str]
    component_count: int
    total_weight_g: int  # sum of known component weights
    created_at: datetime


# ---------- Installed components ----------

class ComponentCreate(BaseModel):
    catalog_id: int
    installed_at: date
    note: Optional[str] = Field(default=None, max_length=500)


class ComponentUpdate(BaseModel):
    installed_at: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=500)


class ComponentOut(BaseModel):
    id: int
    bike_id: int
    installed_at: date
    note: Optional[str]
    last_service_at: Optional[date]
    last_service_mileage_km: Optional[int]
    catalog: CatalogOut


class BikeDetailOut(BikeOut):
    components: list[ComponentOut]


# ---------- Service records ----------

class ServiceCreate(BaseModel):
    done_at: date
    mileage_km: int = Field(ge=0, le=1_000_000)
    note: Optional[str] = Field(default=None, max_length=500)


class ServiceUpdate(BaseModel):
    done_at: Optional[date] = None
    mileage_km: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    note: Optional[str] = Field(default=None, max_length=500)


class ServiceOut(BaseModel):
    id: int
    component_id: int
    done_at: date
    mileage_km: int
    note: Optional[str]
    created_at: datetime


class ServiceHistoryOut(ServiceOut):
    """A service record with context, for the History tab."""
    component_name: str
    component_category: Category
    bike_id: int
    bike_name: str
