"""Deribit instrument name parsing and normalization."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal

from atlas.core.instrument import Instrument, InstrumentRef, InstrumentType, OptionType

# BTC-27JUN26-90000-C or BTC-27JUN26-90000-P
_OPTION_PATTERN = re.compile(
    r"^(?P<base>[A-Z]+)-(?P<expiry>\d{1,2}[A-Z]{3}\d{2})-(?P<strike>\d+(?:\.\d+)?)-(?P<cp>[CP])$"
)
# BTC-28MAR26 dated future
_FUTURE_PATTERN = re.compile(r"^(?P<base>[A-Z]+)-(?P<expiry>\d{1,2}[A-Z]{3}\d{2})$")
_MONTH_MAP = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

INDEX_CHANNEL = "deribit_price_index.btc_usd"
INDEX_SYMBOL = "btc_usd"


def parse_deribit_expiry(expiry: str) -> date:
    """Parse Deribit expiry token like 27JUN26 into a date."""
    match = re.match(r"^(\d{1,2})([A-Z]{3})(\d{2})$", expiry.upper())
    if not match:
        msg = f"Invalid Deribit expiry: {expiry}"
        raise ValueError(msg)
    day, month_str, year = match.groups()
    return date(2000 + int(year), _MONTH_MAP[month_str], int(day))


def parse_deribit_instrument(
    instrument_name: str,
    *,
    kind: str | None = None,
    expiration_timestamp: int | None = None,
    strike: float | None = None,
    option_type: str | None = None,
) -> Instrument:
    """
    Map a Deribit instrument name to the internal Instrument model.

    Uses API metadata when available; falls back to name parsing.
    """
    if instrument_name == "BTC-PERPETUAL" or (
        kind == "future" and "PERPETUAL" in instrument_name.upper()
    ):
        return Instrument(
            exchange_symbol=instrument_name,
            normalized_symbol=instrument_name,
            instrument_type=InstrumentType.PERPETUAL,
        )

    if kind == "spot" or instrument_name in {"BTC_USDC", "BTC_USDT"}:
        return Instrument(
            exchange_symbol=instrument_name,
            normalized_symbol=instrument_name,
            instrument_type=InstrumentType.SPOT,
        )

    option_match = _OPTION_PATTERN.match(instrument_name)
    if option_match or kind == "option":
        expiry_date = None
        strike_val = None
        opt_type = None

        if expiration_timestamp is not None:
            expiry_date = datetime.fromtimestamp(expiration_timestamp / 1000, tz=UTC).date()
        if strike is not None:
            strike_val = Decimal(str(strike))
        if option_type:
            opt_type = OptionType.CALL if option_type == "call" else OptionType.PUT

        if option_match:
            expiry_date = expiry_date or parse_deribit_expiry(option_match.group("expiry"))
            strike_val = strike_val or Decimal(option_match.group("strike"))
            cp = option_match.group("cp")
            opt_type = opt_type or (OptionType.CALL if cp == "C" else OptionType.PUT)

        return Instrument(
            exchange_symbol=instrument_name,
            normalized_symbol=instrument_name,
            instrument_type=InstrumentType.OPTION,
            expiry=expiry_date,
            strike=strike_val,
            option_type=opt_type,
        )

    future_match = _FUTURE_PATTERN.match(instrument_name)
    if future_match or kind == "future":
        expiry_date = None
        if expiration_timestamp is not None:
            expiry_date = datetime.fromtimestamp(expiration_timestamp / 1000, tz=UTC).date()
        elif future_match:
            expiry_date = parse_deribit_expiry(future_match.group("expiry"))

        return Instrument(
            exchange_symbol=instrument_name,
            normalized_symbol=instrument_name,
            instrument_type=InstrumentType.FUTURE,
            expiry=expiry_date,
        )

    return Instrument(
        exchange_symbol=instrument_name,
        normalized_symbol=instrument_name,
        instrument_type=InstrumentType.SPOT,
    )


def instrument_ref_from_name(
    instrument_name: str,
    *,
    kind: str | None = None,
    expiration_timestamp: int | None = None,
    strike: float | None = None,
    option_type: str | None = None,
) -> InstrumentRef:
    """Build InstrumentRef from a Deribit instrument name."""
    return InstrumentRef.from_instrument(
        parse_deribit_instrument(
            instrument_name,
            kind=kind,
            expiration_timestamp=expiration_timestamp,
            strike=strike,
            option_type=option_type,
        )
    )


def index_instrument_ref() -> InstrumentRef:
    """Reference for the BTC USD index price stream."""
    return InstrumentRef(
        exchange_symbol=INDEX_SYMBOL,
        normalized_symbol="BTC-USD-INDEX",
        instrument_type=InstrumentType.INDEX,
    )
