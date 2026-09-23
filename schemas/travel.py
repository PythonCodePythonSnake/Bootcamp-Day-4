"""Pydantic schemas for structured travel request data."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TripIntent(str, Enum):
    FOOD = "food"
    SIGHTSEEING = "sightseeing"
    ADVENTURE = "adventure"
    RELAXATION = "relaxation"
    CULTURAL = "cultural"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class TransportPreference(str, Enum):
    FLIGHT = "flight"
    TRAIN = "train"
    BUS = "bus"
    CAR = "car"
    ANY = "any"


class AccommodationPreference(str, Enum):
    BUDGET = "budget"
    MID_RANGE = "mid_range"
    LUXURY = "luxury"
    ANY = "any"


class DateInfo(BaseModel):
    """Trip dates/duration. Any field may be unknown until clarified."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_days: Optional[int] = None
    month_hint: Optional[str] = None  # e.g. "December" when exact dates unknown


class TravelerInfo(BaseModel):
    num_adults: Optional[int] = None
    num_children: Optional[int] = None
    total_travelers: Optional[int] = None


class BudgetInfo(BaseModel):
    amount: Optional[float] = None
    currency: str = "INR"
    per_person: bool = True
    is_estimate: bool = True


class Preferences(BaseModel):
    interests: list[str] = Field(default_factory=list)  # e.g. ["food", "history"]
    dietary_requirements: list[str] = Field(default_factory=list)
    must_visit: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    transportation: TransportPreference = TransportPreference.ANY
    accommodation: AccommodationPreference = AccommodationPreference.ANY


class MissingInfo(BaseModel):
    """Tracks which essential fields still need to be collected from the user."""

    fields: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return len(self.fields) == 0


class TravelRequest(BaseModel):
    """Central structured representation of the user's trip request."""

    raw_text: str = ""

    origin: Optional[str] = None
    destination: Optional[str] = None

    dates: DateInfo = Field(default_factory=DateInfo)
    travelers: TravelerInfo = Field(default_factory=TravelerInfo)
    budget: BudgetInfo = Field(default_factory=BudgetInfo)
    preferences: Preferences = Field(default_factory=Preferences)

    trip_intent: TripIntent = TripIntent.UNKNOWN

    missing_info: MissingInfo = Field(default_factory=MissingInfo)
    requires_human_input: bool = False

    class Config:
        use_enum_values = False