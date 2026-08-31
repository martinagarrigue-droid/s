"""Copy fijo para el "Diagnóstico Óptico" gratuito (teaser) de la carta.

Deliberadamente NO pasa por report_engine: la vista previa gratuita no debe
disparar el costo de una llamada a Claude. Eso queda reservado al informe
completo, después del pago (ver main.py: /api/calculate vs
/api/generate-report).

Reglas de tono (no negociables, ver directiva de marca):
- Nada de "Sos Tauro y tu ascendente es Virgo" en prosa plana. El signo
  vive en un tag técnico aparte (`sun_sign` / `ascendant_sign`); los
  párrafos hablan en términos de frecuencia, temperatura de luz, densidad
  de aura y geometría — nunca nombran el signo directamente.
- El párrafo personal da un destello de la frecuencia base, no la lectura
  de la carta. El párrafo de clima global menciona la tensión de fondo
  entre Quirón y Vesta y cómo llega a cada temperamento elemental.
- Cierra con un gancho que empuja al informe completo, nunca con la
  lectura resuelta.
"""

SIGN_LABELS_ES = {
    "Aries": "Aries",
    "Taurus": "Tauro",
    "Gemini": "Géminis",
    "Cancer": "Cáncer",
    "Leo": "Leo",
    "Virgo": "Virgo",
    "Libra": "Libra",
    "Scorpio": "Escorpio",
    "Sagittarius": "Sagitario",
    "Capricorn": "Capricornio",
    "Aquarius": "Acuario",
    "Pisces": "Piscis",
}

SIGN_ELEMENTS = {
    "Aries": "fuego",
    "Leo": "fuego",
    "Sagittarius": "fuego",
    "Taurus": "tierra",
    "Virgo": "tierra",
    "Capricorn": "tierra",
    "Gemini": "aire",
    "Libra": "aire",
    "Aquarius": "aire",
    "Cancer": "agua",
    "Scorpio": "agua",
    "Pisces": "agua",
}

# Párrafo 1 — frecuencia base personal, por signo solar. Nunca nombra el
# signo: describe la firma óptica en términos de frecuencia, temperatura,
# densidad y geometría.
SUN_SIGN_PARAGRAPHS = {
    "Aries": (
        "Tu frecuencia base opera en el extremo corto del espectro: alta energía, "
        "baja inercia, encendido casi instantáneo. Es luz de ignición — se activa "
        "antes de que el resto del sistema termine de calibrarse, y por eso rara vez "
        "brilla con la misma intensidad dos veces seguidas sin una fuente externa "
        "que la reactive."
    ),
    "Taurus": (
        "Tu frecuencia base vive en el extremo largo del espectro visible: onda "
        "estable, baja en variación, alta en persistencia. No es una luz que "
        "estalla — es una que se sostiene mucho después de que la fuente que la "
        "encendió ya se apagó, lo cual explica por qué cambiar de dirección te "
        "cuesta más que a la mayoría."
    ),
    "Gemini": (
        "Tu frecuencia base no es una sola onda sino una interferencia entre dos: "
        "dos longitudes distintas ocupando el mismo punto del espectro, alternando "
        "más rápido de lo que el ojo puede resolver. Leído desde afuera parece "
        "dispersión; leído desde dentro es información procesándose en paralelo."
    ),
    "Cancer": (
        "Tu frecuencia base no se emite, se refleja: absorbés la luz ambiental "
        "antes de devolverla, filtrada por una capa de memoria que ninguna otra "
        "configuración lleva incorporada de fábrica. Por eso tu brillo cambia "
        "según lo que tenés cerca, sin que eso lo vuelva menos tuyo."
    ),
    "Leo": (
        "Tu frecuencia base es una fuente de irradiación constante, no reflejada: "
        "emite desde el centro hacia afuera y necesita un receptor — un testigo — "
        "para confirmar que la emisión está llegando. No es una falla del sistema; "
        "es cómo está diseñado para funcionar."
    ),
    "Virgo": (
        "Tu frecuencia base pasa por un filtro de banda angosta: de todo el "
        "espectro disponible, solo deja pasar la porción que puede medirse, "
        "verificarse y corregirse. Es luz de alta resolución antes que de alto "
        "brillo — ilumina el detalle exacto, no el paisaje completo."
    ),
    "Libra": (
        "Tu frecuencia base no proviene de un único punto sino de dos focos en "
        "tensión dinámica, recalculando constantemente el equilibrio entre ambos. "
        "No es indecisión — es un sistema óptico de dos lentes que necesita las "
        "dos posiciones enfocadas para proyectar una sola imagen nítida."
    ),
    "Scorpio": (
        "Tu frecuencia base se comprime antes de emitirse: alta densidad, baja "
        "superficie visible, y una temperatura interna que no se corresponde con "
        "lo que se percibe desde afuera. Lo que parece opaco a simple vista suele "
        "estar incandescente por dentro, bajo presión."
    ),
    "Sagittarius": (
        "Tu frecuencia base es un haz de largo alcance, más ancho de apertura que "
        "de precisión: diseñado para viajar, no para quedarse fijo en un punto "
        "cercano. Pierde intensidad rápido en espacios chicos y la recupera en "
        "cuanto encuentra un horizonte donde proyectarse sin obstáculos."
    ),
    "Capricorn": (
        "Tu frecuencia base es de combustión lenta: tarda en alcanzar su "
        "temperatura de régimen, pero una vez ahí no depende de un estímulo "
        "externo constante para sostenerse. Es luz construida para la larga "
        "duración, no para el destello inicial."
    ),
    "Aquarius": (
        "Tu frecuencia base no es un punto sino un patrón: múltiples emisiones "
        "más débiles por separado, pero coherentes entre sí, formando una "
        "estructura que solo se reconoce al observarla desde la distancia "
        "correcta. De cerca, cada punto puede parecer errático."
    ),
    "Pisces": (
        "Tu frecuencia base no tiene un borde de corte definido: se filtra por "
        "cualquier superficie porosa que encuentre, lo cual la hace difícil de "
        "aislar de la luz ambiental que la rodea. Es una arquitectura permeable "
        "por diseño, no por falta de estructura."
    ),
}

DEFAULT_PARAGRAPH = (
    "Tu frecuencia base todavía no está descrita en este sistema — lo cual, "
    "en sí mismo, ya es una lectura."
)

# Párrafo 2 — clima global de la semana, por elemento. Comparte el mismo
# eje factual (Quirón/Vesta en tensión, Sol todavía en Virgo camino al
# equinoccio) y cierra distinto según cómo aterriza en cada temperamento.
_CHIRON_VESTA_OPENING = (
    "Por estos días, el arquetipo del Sanador Herido (Quirón) sostiene una "
    "fricción de fondo con la Guardiana de la llama (Vesta): la herida que se "
    "resiste a cerrarse del todo, contra la devoción que exige un solo altar. "
    "Bajo el Sol todavía en Virgo, camino al equinoccio, esa tensión "
)

ELEMENT_CLIMATE_PARAGRAPHS = {
    "fuego": (
        _CHIRON_VESTA_OPENING
        + "llega a un núcleo de fuego como impaciencia: con los rituales a "
        "medias, con la fe que se pide entera o no se pide. No es la semana de "
        "resolverlo del todo — es la de notar dónde aparece."
    ),
    "tierra": (
        _CHIRON_VESTA_OPENING
        + "llega a una arquitectura de tierra casi sin ruido: se acumula como "
        "desgaste en la rutina que sostenés sin pedir crédito, no como crisis "
        "visible. No es la semana de resolverlo del todo — es la de notar dónde "
        "se está acumulando."
    ),
    "aire": (
        _CHIRON_VESTA_OPENING
        + "llega a un sistema de aire como resistencia a jurarle lealtad a un "
        "solo punto fijo mientras el patrón completo todavía no terminó de "
        "mapearse. No es la semana de resolverlo del todo — es la de notar de "
        "qué te estás desentendiendo antes de tiempo."
    ),
    "agua": (
        _CHIRON_VESTA_OPENING
        + "se filtra en una configuración de agua antes de poder nombrarse: la "
        "herida y la devoción se mezclan hasta volverse casi indistinguibles. No "
        "es la semana de resolverlo del todo — es la de notar qué estás "
        "confundiendo con qué."
    ),
}

DEFAULT_CLIMATE_PARAGRAPH = _CHIRON_VESTA_OPENING + (
    "atraviesa cualquier configuración que se le cruce. No es la semana de "
    "resolverlo del todo — es la de notar dónde te está tocando."
)

TEASER_HOOK = (
    "Esto es la superficie del fenómeno. La geometría exacta — en qué casa "
    "vive esta tensión, qué aspecto la activa y el resto de tu frecuencia — "
    "se desarrolla únicamente en el informe completo."
)


def build_teaser(chart: dict) -> dict:
    """Arma el Diagnóstico Óptico gratuito a partir del chart de natal_engine."""
    sun = next(p for p in chart["planets"] if p["name"] == "Sun")
    ascendant = chart["angles"]["ascendant"]

    sun_sign_en = sun["sign"]
    ascendant_sign_en = ascendant["sign"]
    element = SIGN_ELEMENTS.get(sun_sign_en)

    return {
        "sun_sign": SIGN_LABELS_ES.get(sun_sign_en, sun_sign_en),
        "ascendant_sign": SIGN_LABELS_ES.get(ascendant_sign_en, ascendant_sign_en),
        "paragraph_one": SUN_SIGN_PARAGRAPHS.get(sun_sign_en, DEFAULT_PARAGRAPH),
        "paragraph_two": ELEMENT_CLIMATE_PARAGRAPHS.get(element, DEFAULT_CLIMATE_PARAGRAPH),
        "hook": TEASER_HOOK,
    }
