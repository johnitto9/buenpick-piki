from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CommerceSummary(ApiModel):
    id: str
    name: str


class PickSummary(ApiModel):
    id: str
    title: str
    description: str
    price: int = Field(ge=0)
    original_price: int = Field(ge=0)
    available_quantity: int = Field(ge=0)
    status: Literal["AVAILABLE"]
    image_url: HttpUrl | None
    commerce: CommerceSummary


class PickSearchResponse(ApiModel):
    items: tuple[PickSummary, ...]
    total: int = Field(ge=0)


class PickupWindow(ApiModel):
    starts_at: datetime
    ends_at: datetime


class Fulfillment(ApiModel):
    pickup: bool
    delivery_enabled: bool
    delivery_eta_min_minutes: int | None = Field(default=None, ge=0)
    delivery_eta_max_minutes: int | None = Field(default=None, ge=0)


class PickConditions(ApiModel):
    quantity_available: int = Field(ge=0)
    approx_weight_grams: int | None = Field(default=None, ge=0)
    fulfillment: Fulfillment


OpeningHours = dict[str, Any] | list[Any] | str | None


class PickCommerce(ApiModel):
    id: str
    name: str
    description: str
    address: str
    city: str
    zone: str
    status: Literal["active"]
    opening_hours: OpeningHours = None


class AvailablePick(ApiModel):
    id: str
    title: str
    description: str
    price: int = Field(ge=0)
    original_price: int = Field(ge=0)
    available_quantity: int = Field(ge=0)
    status: Literal["AVAILABLE"]
    image_url: HttpUrl | None
    images: tuple[HttpUrl, ...]
    category: str
    pickup: PickupWindow
    conditions: PickConditions
    commerce: PickCommerce
    public_url: HttpUrl


class CommerceDelivery(ApiModel):
    enabled: bool
    fee_cents: int | None = Field(default=None, ge=0)
    eta_min_minutes: int | None = Field(default=None, ge=0)
    eta_max_minutes: int | None = Field(default=None, ge=0)


class Commerce(ApiModel):
    id: str
    name: str
    slug: str
    description: str
    address: str
    city: str
    zone: str
    phone: str
    status: Literal["active"]
    opening_hours: OpeningHours = None
    pickup_instructions: str | None
    delivery: CommerceDelivery
    accepts_cash_on_pickup: bool
    logo_url: HttpUrl | None
    cover_url: HttpUrl | None


class OrderCommerce(ApiModel):
    id: str
    name: str
    address: str
    opening_hours: OpeningHours = None


class OrderPick(ApiModel):
    pick_id: str
    title: str
    quantity: int = Field(gt=0)
    unit_price: int = Field(ge=0)
    line_total: int = Field(ge=0)
    image_url: HttpUrl | None


class OrderFulfillment(ApiModel):
    type: Literal["pickup", "delivery"]
    delivery_address: str | None
    delivery_notes: str | None
    pickup_code: str | None


class OrderPickup(ApiModel):
    instructions: str | None
    store_address: str


class OrderDates(ApiModel):
    created_at: datetime
    expires_at: datetime | None
    confirmed_at: datetime | None
    paid_at: datetime | None
    preparing_at: datetime | None
    ready_at: datetime | None
    out_for_delivery_at: datetime | None
    delivered_at: datetime | None
    picked_up_at: datetime | None


class CustomerOrder(ApiModel):
    id: str
    status: str
    commerce: OrderCommerce
    picks: tuple[OrderPick, ...]
    total: int = Field(ge=0)
    fulfillment: OrderFulfillment
    pickup: OrderPickup
    dates: OrderDates


def format_ars_cents(cents: int) -> str:
    if cents < 0:
        raise ValueError("ARS cents cannot be negative")
    amount = Decimal(cents) / Decimal(100)
    whole, decimal = f"{amount:,.2f}".split(".")
    localized_whole = whole.replace(",", ".")
    return f"${localized_whole},{decimal}"

