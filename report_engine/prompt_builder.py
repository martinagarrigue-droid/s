"""Arma el contexto y las directivas de prompt a partir del JSON de la Etapa 1.

Este modulo es puro formateo de texto: no llama a la API. Separarlo de
generator.py permite testearlo sin mockear el cliente de Anthropic.
"""

from report_engine.config import ASPECTS_ES, BODIES_ES, SIGNS_ES


def _format_degree(sign_degree: float) -> str:
    """23.67 -> "23°40'\""""
    degrees = int(sign_degree)
    minutes = int(round((sign_degree - degrees) * 60))
    if minutes == 60:
        minutes = 0
        degrees += 1
    return f"{degrees}°{minutes:02d}'"


def _body_es(name: str) -> str:
    return BODIES_ES.get(name, name)


def _sign_es(name: str) -> str:
    return SIGNS_ES.get(name, name)


def format_natal_summary(chart: dict) -> str:
    """Convierte el dict de generate_natal_chart en texto legible en espanol.

    Este es el bloque que se cachea (cache_control) y se reusa identico en
    las N llamadas de un mismo informe -- ver report_engine/generator.py.
    """
    subject = chart["subject"]
    birth = subject["birth"]
    place = subject["place"]
    meta = chart["meta"]

    lines = []
    lines.append("=== DATOS DE NACIMIENTO ===")
    lines.append(f"Nombre: {subject['name']}")
    lines.append(f"Fecha y hora local de nacimiento: {birth['local_datetime']}")
    place_desc = place.get("resolved_display_name") or place.get("input_text") or "N/D"
    lines.append(f"Lugar: {place_desc} (lat {place['latitude']:.4f}, lon {place['longitude']:.4f})")
    lines.append(f"Sistema de casas: {meta['engine']['house_system']}")
    lines.append("")

    lines.append("=== ANGULOS ===")
    for angle_key, label in (
        ("ascendant", "Ascendente"), ("midheaven", "Medio Cielo"),
        ("descendant", "Descendente"), ("imum_coeli", "Fondo del Cielo"),
    ):
        angle = chart["angles"][angle_key]
        lines.append(f"{label}: {_sign_es(angle['sign'])} {_format_degree(angle['sign_degree'])}")
    lines.append("")

    lines.append("=== PLANETAS Y PUNTOS ===")
    for planet in chart["planets"]:
        retro = " (retrogrado)" if planet["retrograde"] else ""
        lines.append(
            f"{_body_es(planet['name'])}: {_sign_es(planet['sign'])} "
            f"{_format_degree(planet['sign_degree'])}, casa {planet['house']}{retro}"
        )
    lines.append("")

    lines.append("=== CASAS ===")
    for house in chart["houses"]:
        lines.append(
            f"Casa {house['number']}: {_sign_es(house['sign'])} "
            f"{_format_degree(house['sign_degree'])} "
            f"(regente tradicional: {_body_es(house['ruler'])})"
        )
    lines.append("")

    lines.append("=== ASPECTOS MAYORES ===")
    if not chart["aspects"]:
        lines.append("(sin aspectos mayores dentro de orbe)")
    for aspect in chart["aspects"]:
        applying = "aplicativo" if aspect["applying"] else "separativo"
        lines.append(
            f"{_body_es(aspect['body_a'])} {ASPECTS_ES.get(aspect['type'], aspect['type'])} "
            f"{_body_es(aspect['body_b'])} (orbe {aspect['orb']:.2f}°, {applying})"
        )

    return "\n".join(lines)


def build_section_user_message(section: dict, chart: dict) -> str:
    """Arma el mensaje de usuario (directiva especifica) para una seccion.

    El contexto natal completo NO va aca -- vive en el bloque cacheado del
    system prompt (ver generator.py) para no pagarlo N veces.
    """
    parts = [f"SECCION A ESCRIBIR: {section['title']}", "", section["directive"]]

    if section["kind"] == "planets":
        bodies_es = ", ".join(_body_es(b) for b in section["bodies"])
        parts.append("")
        parts.append(f"Cuerpos a cubrir en esta seccion: {bodies_es}.")

    return "\n".join(parts)
