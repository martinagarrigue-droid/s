"""Tests del calculo de aspectos."""

from natal_engine.aspects import AspectBody, compute_aspects


def test_exact_conjunction_detected():
    bodies = [
        AspectBody("Sun", 100.0, speed_longitude=1.0),
        AspectBody("Moon", 101.0, speed_longitude=13.0),
    ]
    aspects = compute_aspects(bodies)
    assert len(aspects) == 1
    assert aspects[0]["type"] == "conjunction"
    assert aspects[0]["orb"] == 1.0


def test_no_aspect_outside_all_orbs():
    bodies = [
        AspectBody("Sun", 0.0, speed_longitude=1.0),
        AspectBody("Moon", 40.0, speed_longitude=13.0),  # no cae en ningun aspecto mayor
    ]
    assert compute_aspects(bodies) == []


def test_opposition_across_zero_degrees():
    bodies = [
        AspectBody("Sun", 5.0, speed_longitude=1.0),
        AspectBody("Mars", 183.0, speed_longitude=0.5),
    ]
    aspects = compute_aspects(bodies)
    assert len(aspects) == 1
    assert aspects[0]["type"] == "opposition"
    assert aspects[0]["orb"] == 2.0


def test_custom_orb_override():
    bodies = [AspectBody("Sun", 0.0), AspectBody("Venus", 7.5)]
    # 7.5 de orb en conjuncion: por defecto (8) entra, con override (5) no.
    assert len(compute_aspects(bodies)) == 1
    assert compute_aspects(bodies, orbs={"conjunction": 5}) == []


def test_angle_body_zero_speed_still_detects_applying():
    # Asc "fijo" (speed=0), planeta acercandose -> deberia marcar applying=True.
    bodies = [
        AspectBody("Ascendant", 100.0, speed_longitude=0.0),
        AspectBody("Mars", 95.0, speed_longitude=0.5),
    ]
    aspects = compute_aspects(bodies)
    assert len(aspects) == 1
    assert aspects[0]["applying"] is True


def test_only_one_aspect_type_per_pair():
    bodies = [AspectBody("Sun", 0.0), AspectBody("Moon", 2.0)]
    aspects = compute_aspects(bodies)
    assert len(aspects) == 1
