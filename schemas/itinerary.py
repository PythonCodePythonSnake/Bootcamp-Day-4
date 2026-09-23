"""Pydantic schemas for structured itinerary output."""

from __future__ import annotations

from datetime import date, time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    """Provenance for a piece of data, so estimates vs verified facts are distinguishable."""

    source: str = "unknown"  # e.g. "google_places", "web_search", "llm_estimate"
    url: Optional[str] = None
    is_verified: bool = False  # True if came from a live external API call


class Coordinates(BaseModel):
    lat: float
    lng: float


class Place(BaseModel):
    """A sightseeing attraction, museum, activity, or point of interest."""

    name: str
    category: Optional[str] = None  # e.g. "museum", "landmark", "activity"
    description: Optional[str] = None
    address: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    opening_hours: Optional[str] = None
    price: Optional[float] = None
    currency: str = "INR"
    rating: Optional[float] = None
    tags: list[str] = Field(default_factory=list)
    source_info: SourceInfo = Field(default_factory=SourceInfo)


class Restaurant(BaseModel):
    name: str
    cuisine: list[str] = Field(default_factory=list)
    price_range: Optional[str] = None  # e.g. "$", "$$", "$$$"
    address: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    opening_hours: Optional[str] = None
    rating: Optional[float] = None
    dietary_options: list[str] = Field(default_factory=list)
    source_info: SourceInfo = Field(default_factory=SourceInfo)


class Hotel(BaseModel):
    name: str
    address: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    price_per_night: Optional[float] = None
    currency: str = "INR"
    rating: Optional[float] = None
    amenities: list[str] = Field(default_factory=list)
    distance_to_center_km: Optional[float] = None
    source_info: SourceInfo = Field(default_factory=SourceInfo)


class TransportMode(str, Enum):
    FLIGHT = "flight"
    TRAIN = "train"
    BUS = "bus"
    CAR = "car"
    LOCAL = "local"  # taxi/auto/metro within the destination


class TransportOption(BaseModel):
    mode: TransportMode
    provider: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    price: Optional[float] = None
    currency: str = "INR"
    source_info: SourceInfo = Field(default_factory=SourceInfo)


class RouteLeg(BaseModel):
    origin: str
    destination: str
    distance_km: Optional[float] = None
    duration_minutes: Optional[int] = None
    mode: str = "driving"


class Route(BaseModel):
    """An ordered set of legs, e.g. for a day's sightseeing loop."""

    legs: list[RouteLeg] = Field(default_factory=list)
    total_distance_km: Optional[float] = None
    total_duration_minutes: Optional[int] = None
    optimized_order: list[str] = Field(default_factory=list)  # place names in visit order
    source_info: SourceInfo = Field(default_factory=SourceInfo)


class ActivityBlock(BaseModel):
    """A single scheduled item within a day (place visit, meal, transit)."""

    time_slot: Optional[str] = None  # e.g. "morning", "09:00-11:00"
    activity_type: str  # "sightseeing", "meal", "transport", "hotel_checkin", etc.
    place: Optional[Place] = None
    restaurant: Optional[Restaurant] = None
    transport: Optional[TransportOption] = None
    notes: Optional[str] = None
    estimated_cost: Optional[float] = None
    is_estimate: bool = True


class DayPlan(BaseModel):
    day_number: int
    date: Optional[date] = None
    blocks: list[ActivityBlock] = Field(default_factory=list)
    route: Optional[Route] = None
    hotel: Optional[Hotel] = None
    daily_estimated_cost: Optional[float] = None
    summary: Optional[str] = None


class Itinerary(BaseModel):
    """Final synthesized itinerary."""

    destination: str
    origin: Optional[str] = None
    day_plans: list[DayPlan] = Field(default_factory=list)
    total_estimated_cost: Optional[float] = None
    currency: str = "INR"
    transport_options: list[TransportOption] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    version: int = 1  # incremented on each regeneration/modification