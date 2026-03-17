from datetime import UTC, date, datetime

from app.services.nse_clock import NseMarketClock


def test_market_clock_open_during_session():
    clock = NseMarketClock()
    dt = datetime(2026, 3, 16, 4, 5, tzinfo=UTC)  # 09:35 IST Monday
    assert clock.is_market_open(dt) is True


def test_market_clock_closed_after_session():
    clock = NseMarketClock()
    dt = datetime(2026, 3, 16, 11, 15, tzinfo=UTC)  # 16:45 IST Monday
    assert clock.is_market_open(dt) is False


def test_market_clock_closed_on_holiday():
    clock = NseMarketClock()
    clock._holiday_dates = {date(2026, 3, 16)}
    dt = datetime(2026, 3, 16, 4, 5, tzinfo=UTC)  # 09:35 IST Monday
    assert clock.is_market_open(dt) is False
