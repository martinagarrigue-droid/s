"""Calculo de aspectos mayores entre cuerpos (planetas, nodos, angulos)."""

from dataclasses import dataclass

from natal_engine.config import ASPECTS, DEFAULT_ASPECT_ORBS


@dataclass
class AspectBody:
    """Un punto del cielo que puede participar en aspectos.

    speed_longitude=0.0 para Ascendente/Medio Cielo: en una carta natal son
    posiciones fijas del instante de nacimiento igual que los planetas, pero
    no tienen un movimiento orbital propio con el que calcular
    aplicacion/separacion -- se usa solo la velocidad del otro cuerpo.
    """

    name: str
    longitude: float
    speed_longitude: float = 0.0


def _angular_separation(lon_a: float, lon_b: float) -> float:
    """Separacion angular minima entre dos longitudes, en rango [0, 180]."""
    diff = abs(lon_a - lon_b) % 360
    return 360 - diff if diff > 180 else diff


def _is_applying(
    lon_a: float, lon_b: float, speed_a: float, speed_b: float, exact_angle: float
) -> bool:
    """True si el aspecto se esta formando (orb decreciente), False si se aleja."""
    dt_days = 0.01
    sep_now = _angular_separation(lon_a, lon_b)
    future_a = lon_a + speed_a * dt_days
    future_b = lon_b + speed_b * dt_days
    sep_future = _angular_separation(future_a, future_b)
    return abs(sep_future - exact_angle) < abs(sep_now - exact_angle)


def compute_aspects(bodies: list[AspectBody], orbs: dict | None = None) -> list[dict]:
    """Calcula todos los aspectos mayores entre pares de `bodies` dentro del orbe.

    orbs: dict opcional {'conjunction': 8, ...} que sobreescribe
    DEFAULT_ASPECT_ORBS. Cualquier aspecto no listado usa el default.
    """
    active_orbs = {**DEFAULT_ASPECT_ORBS, **(orbs or {})}
    results = []

    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            body_a, body_b = bodies[i], bodies[j]
            separation = _angular_separation(body_a.longitude, body_b.longitude)

            for aspect_name, exact_angle in ASPECTS.items():
                orb_limit = active_orbs[aspect_name]
                orb = abs(separation - exact_angle)
                if orb <= orb_limit:
                    results.append({
                        "body_a": body_a.name,
                        "body_b": body_b.name,
                        "type": aspect_name,
                        "exact_angle": exact_angle,
                        "actual_separation": round(separation, 4),
                        "orb": round(orb, 4),
                        "applying": _is_applying(
                            body_a.longitude, body_b.longitude,
                            body_a.speed_longitude, body_b.speed_longitude,
                            exact_angle,
                        ),
                    })
                    # Un mismo par de cuerpos solo puede formar un aspecto
                    # mayor a la vez (los angulos exactos no se solapan
                    # dentro de orbes estandar), no hace falta seguir
                    # probando el resto de aspectos para este par.
                    break

    return results
