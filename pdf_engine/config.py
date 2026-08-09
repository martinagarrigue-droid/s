"""Configuración de la Etapa 3: textos fijos de la portada y presentación.

El diseño (color, tipografía, layout) vive en styles.css -- este archivo es
solo texto y datos, para no mezclar contenido con estilo.
"""

PAGE_SIZE = "A4"

COVER_EYEBROW = "Informe de carta natal"
COVER_FOOTER_LABEL = "Documento confidencial · uso personal"

MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

COVER_FIELD_LABELS = {
    "birth": "Nacimiento",
    "place": "Lugar",
    "house_system": "Sistema de casas",
}
