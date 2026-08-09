"""Tests de las funciones puras de geometria (sin red, sin swisseph vivo)."""

import pytest

from natal_engine.ephemeris import find_house_of_longitude, local_to_utc, longitude_to_sign
from natal_engine.exceptions import InvalidDateTimeError


class TestLongitudeToSign:
    def test_zero_degrees_is_start_of_aries(self):
        sign, degree = longitude_to_sign(0.0)
        assert sign == "Aries"
        assert degree == pytest.approx(0.0)

    def test_middle_of_taurus(self):
        sign, degree = longitude_to_sign(45.0)
        assert sign == "Taurus"
        assert degree == pytest.approx(15.0)

    def test_end_of_pisces_wraps(self):
        sign, degree = longitude_to_sign(359.9)
        assert sign == "Pisces"
        assert degree == pytest.approx(29.9)

    def test_negative_longitude_wraps(self):
        sign, degree = longitude_to_sign(-10.0)
        assert sign == "Pisces"
        assert degree == pytest.approx(20.0)

    def test_exactly_360_wraps_to_aries(self):
        sign, degree = longitude_to_sign(360.0)
        assert sign == "Aries"
        assert degree == pytest.approx(0.0)


class TestFindHouseOfLongitude:
    # Cusps parejos de 30 grados, casa 1 empieza en 0 (caso simple tipo Equal).
    EVEN_CUSPS = tuple(i * 30 for i in range(12))

    def test_start_of_house_1(self):
        assert find_house_of_longitude(0.0, self.EVEN_CUSPS) == 1

    def test_middle_of_house_5(self):
        assert find_house_of_longitude(135.0, self.EVEN_CUSPS) == 5

    def test_house_12_wraps_around_zero(self):
        wrap_cusps = (10, 40, 70, 100, 130, 160, 190, 220, 250, 280, 310, 340)
        assert find_house_of_longitude(350.0, wrap_cusps) == 12
        assert find_house_of_longitude(5.0, wrap_cusps) == 12
        assert find_house_of_longitude(15.0, wrap_cusps) == 1


class TestLocalToUtc:
    def test_buenos_aires_offset(self):
        local_dt, utc_dt = local_to_utc("1990-05-14", "14:32", "America/Argentina/Buenos_Aires")
        assert local_dt.hour == 14
        assert local_dt.minute == 32
        assert utc_dt.hour == 17
        assert utc_dt.utcoffset().total_seconds() == 0

    def test_invalid_date_raises(self):
        with pytest.raises(InvalidDateTimeError):
            local_to_utc("14-05-1990", "14:32", "America/Argentina/Buenos_Aires")

    def test_invalid_timezone_raises(self):
        with pytest.raises(InvalidDateTimeError):
            local_to_utc("1990-05-14", "14:32", "Not/A_Real_Zone")

    def test_seconds_precision_supported(self):
        local_dt, _ = local_to_utc("1990-05-14", "14:32:07", "America/Argentina/Buenos_Aires")
        assert local_dt.second == 7
