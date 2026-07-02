"""Instrument model — exchange-agnostic internal representation."""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class InstrumentType(StrEnum):
    SPOT = "spot"
    INDEX = "index"
    PERPETUAL = "perpetual"
    FUTURE = "future"
    OPTION = "option"


class OptionType(StrEnum):
    CALL = "call"
    PUT = "put"


class Instrument(BaseModel):
    """Normalized instrument identity. Payload retains original exchange values."""

    exchange_symbol: str
    normalized_symbol: str
    instrument_type: InstrumentType
    expiry: date | None = None
    strike: Decimal | None = None
    option_type: OptionType | None = None

    model_config = {"frozen": True}


class InstrumentRef(BaseModel):
    """Lightweight instrument reference for events without full normalization."""

    exchange_symbol: str
    normalized_symbol: str | None = None
    instrument_type: InstrumentType | None = None
    expiry: date | None = None
    strike: Decimal | None = None
    option_type: OptionType | None = None

    model_config = {"frozen": True}

    @classmethod
    def from_instrument(cls, instrument: Instrument) -> "InstrumentRef":
        return cls(
            exchange_symbol=instrument.exchange_symbol,
            normalized_symbol=instrument.normalized_symbol,
            instrument_type=instrument.instrument_type,
            expiry=instrument.expiry,
            strike=instrument.strike,
            option_type=instrument.option_type,
        )

    def to_instrument(self) -> Instrument:
        return Instrument(
            exchange_symbol=self.exchange_symbol,
            normalized_symbol=self.normalized_symbol or self.exchange_symbol,
            instrument_type=self.instrument_type or InstrumentType.SPOT,
            expiry=self.expiry,
            strike=self.strike,
            option_type=self.option_type,
        )
