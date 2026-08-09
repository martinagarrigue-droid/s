"""Configuracion de la Etapa 2: modelo, tono y estructura del informe.

Igual que en natal_engine/config.py: todo lo que sea "regla de producto"
(tono, secciones, modelo) vive aca, separado de la logica de llamado a la API.
"""

# claude-opus-4-8 es el default recomendado para este tipo de tarea
# (analitica, generacion larga, alto ticket). Configurable por parametro --
# bajar a "claude-sonnet-5" si el costo por informe pesa en el margen.
DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_EFFORT = "high"
DEFAULT_MAX_TOKENS_PER_SECTION = 8000

# ---------------------------------------------------------------------------
# Traducciones para presentar la carta al LLM en espanol (el schema de
# natal_engine es todo en ingles a proposito, para no atarlo a un idioma).
# ---------------------------------------------------------------------------
SIGNS_ES = {
    "Aries": "Aries", "Taurus": "Tauro", "Gemini": "Géminis", "Cancer": "Cáncer",
    "Leo": "Leo", "Virgo": "Virgo", "Libra": "Libra", "Scorpio": "Escorpio",
    "Sagittarius": "Sagitario", "Capricorn": "Capricornio", "Aquarius": "Acuario",
    "Pisces": "Piscis",
}

BODIES_ES = {
    "Sun": "Sol", "Moon": "Luna", "Mercury": "Mercurio", "Venus": "Venus",
    "Mars": "Marte", "Jupiter": "Júpiter", "Saturn": "Saturno", "Uranus": "Urano",
    "Neptune": "Neptuno", "Pluto": "Plutón", "North Node": "Nodo Norte",
    "South Node": "Nodo Sur", "Ascendant": "Ascendente", "Midheaven": "Medio Cielo",
    "Descendant": "Descendente", "Imum Coeli": "Fondo del Cielo",
}

ASPECTS_ES = {
    "conjunction": "conjunción", "opposition": "oposición", "square": "cuadratura",
    "trine": "trígono", "sextile": "sextil",
}

# ---------------------------------------------------------------------------
# Tono: esto es lo unico que se cachea igual en TODOS los informes (nunca
# cambia entre clientes), separado del bloque de datos natales que se cachea
# por-informe. Ver report_engine/generator.py para el uso de cache_control.
# ---------------------------------------------------------------------------
SYSTEM_TONE_INSTRUCTIONS = """Sos un analista psicológico que usa el lenguaje simbólico de la \
astrología como marco descriptivo de patrones de personalidad -- no como \
predicción, no como new age. Escribís para un cliente que paga por un \
informe de alto nivel y espera profundidad analítica real, no un horóscopo \
de revista.

REGLAS DE TONO (no negociables):
- Prohibido: lenguaje místico ("el universo te tiene preparado...", "la \
energía cósmica..."), predicciones deterministas ("vas a conocer a \
alguien", "este año te va a ir bien en..."), tono esotérico o de \
autoayuda genérica, frases que podrían aplicar a cualquier persona.
- Cada posición se describe en términos de FUNCIÓN psicológica: qué \
mecanismo activa, cómo se expresa cuando está integrado (luz) y cómo se \
expresa cuando no (sombra). Nunca "bueno" o "malo" sin esa doble cara.
- Cada afirmación tiene que poder conectarse a un patrón de comportamiento \
observable, no a un destino o evento futuro.
- Nada de disclaimers tipo "esto no determina tu personalidad" ni relleno \
motivacional vacío.
- Segunda persona ("vos", "tenés"), tono de analista agudo que no le tiene \
miedo a nombrar lo incómodo, sin ser cruel porque sí.
- No repitas la definición genérica de cada signo o planeta como apertura \
(evitar "Marte representa la acción"). Andá directo al análisis de ESTA \
carta particular, con sus grados, casas y aspectos específicos.
- Prosa corrida, sin bullet points ni tablas. Párrafos densos y trabajados, \
como un informe clínico bien escrito, no una lista de características."""

# ---------------------------------------------------------------------------
# Secciones del informe, en orden de generacion. Cada seccion es una llamada
# separada a la API -- evita truncamiento y permite reintentos puntuales sin
# regenerar el informe entero.
# ---------------------------------------------------------------------------
SECTIONS = [
    {
        "key": "introduccion",
        "title": "Introducción operativa",
        "kind": "intro",
        "directive": (
            "Escribí la introducción operativa del informe (aprox. 1 página). "
            "Presenta el marco general de esta carta: el patrón dominante que "
            "atraviesa todo (elemento o modalidad predominante si hay uno "
            "claro, la tensión o el eje central que organiza la personalidad), "
            "y cómo se va a leer el resto del informe. No repitas datos "
            "técnicos (signos, grados) que se van a desarrollar después -- "
            "esto es el mapa, no el territorio."
        ),
    },
    {
        "key": "identidad_nuclear",
        "title": "Identidad nuclear: Sol, Luna, Ascendente",
        "kind": "planets",
        "bodies": ["Sun", "Moon", "Ascendant"],
        "directive": (
            "Analizá en profundidad el trío Sol-Luna-Ascendente de esta carta: "
            "el motor de identidad consciente (Sol), el patrón emocional "
            "automático (Luna) y la interfaz con la que la persona se "
            "presenta y procesa el entorno (Ascendente). No los trates como "
            "tres bloques separados -- señalá dónde se refuerzan, dónde "
            "friccionan entre sí, y qué combinación resulta única en esta carta."
        ),
    },
    {
        "key": "estilo_relacional",
        "title": "Estilo cognitivo, relacional y pulsional",
        "kind": "planets",
        "bodies": ["Mercury", "Venus", "Mars"],
        "directive": (
            "Analizá Mercurio (estilo cognitivo y de comunicación), Venus "
            "(patrón de vínculo y de deseo) y Marte (cómo se moviliza el "
            "impulso, la agresión y la asertividad) en esta carta específica. "
            "Luces y sombras funcionales de cada uno según su signo, casa y "
            "aspectos principales."
        ),
    },
    {
        "key": "estructura_expansion",
        "title": "Estructura y expansión",
        "kind": "planets",
        "bodies": ["Jupiter", "Saturn"],
        "directive": (
            "Analizá Júpiter (dónde busca expansión, sentido y exceso) y "
            "Saturno (dónde construye estructura, y dónde opera el miedo o "
            "la autoexigencia) en esta carta. Esta es la tensión central "
            "entre expandirse y contenerse -- desarrollala como tal, no como "
            "dos entradas independientes."
        ),
    },
    {
        "key": "capas_profundas",
        "title": "Capas generacionales y profundas",
        "kind": "planets",
        "bodies": ["Uranus", "Neptune", "Pluto"],
        "directive": (
            "Analizá Urano, Neptuno y Plutón en esta carta -- foco en la casa "
            "donde caen (que es lo personal/individual de una energía "
            "generacional) y en los aspectos que forman con planetas "
            "personales. Evitá el tono grandilocuente típico de estos tres; "
            "tratá cada uno como un patrón psicológico específico y "
            "funcional, no como una fuerza cósmica."
        ),
    },
    {
        "key": "ejes_proposito",
        "title": "Ejes de propósito y vocación",
        "kind": "planets",
        "bodies": ["North Node", "South Node", "Midheaven"],
        "directive": (
            "Analizá el eje Nodo Norte / Nodo Sur (la dirección de "
            "crecimiento versus la zona de confort automática) y el Medio "
            "Cielo (la imagen pública y vocacional) de esta carta. Conectá "
            "explícitamente esto con lo ya descrito en identidad nuclear: "
            "hacia dónde empuja el desarrollo de esta persona."
        ),
    },
    {
        "key": "aspectos",
        "title": "Patrones de aspectos dominantes",
        "kind": "aspects",
        "directive": (
            "Tomando la lista completa de aspectos mayores de esta carta, "
            "identificá y desarrollá los 3 a 5 patrones estructurales más "
            "relevantes (los de orbe más ajustado, los que involucran "
            "luminarias o ángulos, o los que se repiten formando una figura "
            "-- ej. varios aspectos sobre el mismo planeta). No listes todos "
            "los aspectos uno por uno: identificá el patrón que organizan en "
            "conjunto y qué dice sobre cómo esta persona maneja tensión "
            "interna versus fluidez."
        ),
    },
    {
        "key": "sintesis",
        "title": "Síntesis final accionable",
        "kind": "synthesis",
        "directive": (
            "Cerrá el informe con una síntesis final accionable (aprox. 1 "
            "página). No repitas lo ya dicho sección por sección -- integrá "
            "los patrones centrales de la carta en una lectura unificada de "
            "hacia dónde tiende esta personalidad bajo presión y en su mejor "
            "versión, y qué es lo primero que valdría la pena trabajar. Tiene "
            "que leerse como una conclusión clínica, no como un resumen."
        ),
    },
]
