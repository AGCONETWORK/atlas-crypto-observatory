"""Tests for Deribit instrument parsing."""

from datetime import date
from decimal import Decimal

import pytest

from atlas.adapters.deribit.instruments import (
    INDEX_CHANNEL,
    index_instrument_ref,
    parse_deribit_expiry,
    parse_deribit_instrument,
)
from atlas.core.instrument import InstrumentType, OptionType


def test_parse_expiry() -> None:
    assert parse_deribit_expiry("27JUN26") == date(2026, 6, 27)


def test_parse_perpetual() -> None:
    inst = parse_deribit_instrument("BTC-PERPETUAL")
    assert inst.instrument_type == InstrumentType.PERPETUAL


def test_parse_option() -> None:
    inst = parse_deribit_instrument("BTC-27JUN26-90000-C")
    assert inst.instrument_type == InstrumentType.OPTION
    assert inst.expiry == date(2026, 6, 27)
    assert inst.strike == Decimal("90000")
    assert inst.option_type == OptionType.CALL


def test_parse_dated_future() -> None:
    inst = parse_deribit_instrument("BTC-28MAR26")
    assert inst.instrument_type == InstrumentType.FUTURE
    assert inst.expiry == date(2026, 3, 28)


def test_index_ref() -> None:
    ref = index_instrument_ref()
    assert ref.instrument_type == InstrumentType.INDEX
    assert INDEX_CHANNEL == "deribit_price_index.btc_usd"


def test_invalid_expiry() -> None:
    with pytest.raises(ValueError, match="Invalid Deribit expiry"):
        parse_deribit_expiry("BAD")
