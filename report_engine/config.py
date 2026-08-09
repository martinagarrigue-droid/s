"""Configuracion de la Etapa 2: modelo, tono y estructura del informe.

Igual que en natal_engine/config.py: todo lo que sea "regla de producto"
(tono, secciones, modelo) vive aca, separado de la logica de llamado a la API.
"""

# claude-opus-5 es el default recomendado para este tipo de tarea (analitica,
# generacion larga, alto ticket). Configurable via parametro o env var
# ANTHROPIC_MODEL si se quiere bajar de tier por costo.
DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "high"
DEFAULT_MAX_TOKENS_PER_SECTION = 8000

# ---------------------------------------------------------------------------
# Traducciones para presentar la carta al LLM en espanol (el schema de
# natal_engine es todo en ingles a proposito, para no atarlo a un idioma).
# ---------------------------------------------------------------------------
SIGNS_ES = {
    "Aries": "Aries", "Taurus": "Tauro", "Gemini": "Geminis", "Cancer": "Cancer",
    "Leo": "Leo", "Virgo": "Virgo", "Libra": "Libra", "Scorpio": "Escorpio",
    "Sagittarius": "Sagitario", "Capricorn": "Capricornio", "Aquarius": "Acuario",
    "Pisces": "Piscis",
}

BODIES_ES = {
    "Sun": "Sol", "Moon": "Luna", "Mercury": "Mercurio", "Venus": "Venus",
    "Mars": "Marte", "Jupiter": "Jupiter", "Saturn": "Saturno", "Uranus": "Urano",
    "Neptune": "Neptuno", "Pluto": "Pluton", "North Node": "Nodo Norte",
    "South Node": "Nodo Sur", "Ascendant": "Ascendente", "Midheaven": "Medio Cielo",
    "Descendant": "Descendente", "Imum Coeli": "Fondo del Cielo",
}

ASPECTS_ES = {
    "conjunction": "conjuncion", "opposition": "oposicion", "square": "cuadratura",
    "trine": "trigono", "sextile": "sextil",
}

# ---------------------------------------------------------------------------
# Tono: esto es lo unico que se cachea igual en TODOS los informes (nunca
# cambia entre clientes), separado del bloque de datos natales que se cachea
# por-informe. Ver report_engine/generator.py para el uso de cache_control.
# ---------------------------------------------------------------------------
SYSTEM_TONE_INSTRUCTIONS = """Sos un analista psicologico que usa el lenguaje simbolico de la \
astrologia como marco descriptivo de patrones de personalidad -- no como \
prediccion, no como new age. Escribis para un cliente que paga por un \
informe de alto nivel y espera profundidad analitica real, no un horoscopo \
de revista.

REGLAS DE TONO (no negociables):
- Prohibido: lenguaje mistico ("el universo te tiene preparado...", "la \
energia cosmica..."), predicciones deterministas ("vas a conocer a \
alguien", "este anio te va a ir bien en..."), tono esoterico o de \
autoayuda generica, frases que podrian aplicar a cualquier persona.
- Cada posicion se describe en terminos de FUNCION psicologica: que \
mecanismo activa, como se expresa cuando esta integrado (luz) y como se \
expresa cuando no (sombra). Nunca "bueno" o "malo" sin esa doble cara.
- Cada afirmacion tiene que poder conectarse a un patron de comportamiento \
observable, no a un destino o evento futuro.
- Nada de disclaimers tipo "esto no determina tu personalidad" ni relleno \
motivacional vacio.
- Segunda persona ("vos", "tenes"), tono de analista agudo que no le tiene \
miedo a nombrar lo incomodo, sin ser cruel porque si.
- No repitas la definicion generica de cada signo o planeta como apertura \
(evitar "Marte representa la accion"). Anda directo al analisis de ESTA \
carta particular, con sus grados, casas y aspectos especificos.
- Prosa corrida, sin bullet points ni tablas. Parrafos densos y trabajados, \
como un informe clinico bien escrito, no una lista de caracteristicas."""

# ---------------------------------------------------------------------------
# Secciones del informe, en orden de generacion. Cada seccion es una llamada
# separada a la API -- evita truncamiento y permite reintentos puntuales sin
# regenerar el informe entero.
# ---------------------------------------------------------------------------
SECTIONS = [
    {
        "key": "introduccion",
        "title": "Introduccion operativa",
        "kind": "intro",
        "directive": (
            "Escribi la introduccion operativa del informe (aprox. 1 pagina). "
            "Presenta el marco general de esta carta: el patron dominante que "
            "atraviesa todo (elemento o modalidad predominante si hay uno "
            "claro, la tension o el eje central que organiza la personalidad), "
            "y como se va a leer el resto del informe. No repitas datos "
            "tecnicos (signos, grados) que se van a desarrollar despues -- "
            "esto es el mapa, no el territorio."
        ),
    },
    {
        "key": "identidad_nuclear",
        "title": "Identidad nuclear: Sol, Luna, Ascendente",
        "kind": "planets",
        "bodies": ["Sun", "Moon", "Ascendant"],
        "directive": (
            "Analiza en profundidad el trio Sol-Luna-Ascendente de esta carta: "
            "el motor de identidad consciente (Sol), el patron emocional "
            "automatico (Luna) y la interfaz con la que la persona se "
            "presenta y procesa el entorno (Ascendente). No los trates como "
            "tres bloques separados -- señala donde se refuerzan, donde "
            "friccionan entre si, y que combinacion resulta unica en esta carta."
        ),
    },
    {
        "key": "estilo_relacional",
        "title": "Estilo cognitivo, relacional y pulsional",
        "kind": "planets",
        "bodies": ["Mercury", "Venus", "Mars"],
        "directive": (
            "Analiza Mercurio (estilo cognitivo y de comunicacion), Venus "
            "(patron de vinculo y de deseo) y Marte (como se moviliza el "
            "impulso, la agresion y la asertividad) en esta carta especifica. "
            "Luces y sombras funcionales de cada uno segun su signo, casa y "
            "aspectos principales."
        ),
    },
    {
        "key": "estructura_expansion",
        "title": "Estructura y expansion",
        "kind": "planets",
        "bodies": ["Jupiter", "Saturn"],
        "directive": (
            "Analiza Jupiter (donde busca expansion, sentido y exceso) y "
            "Saturno (donde construye estructura, y donde opera el miedo o "
            "la autoexigencia) en esta carta. Esta es la tension central "
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
            "Analiza Urano, Neptuno y Pluton en esta carta -- foco en la casa "
            "donde caen (que es lo personal/individual de una energia "
            "generacional) y en los aspectos que forman con planetas "
            "personales. Evita el tono grandilocuente tipico de estos tres; "
            "trata cada uno como un patron psicologico especifico y "
            "funcional, no como una fuerza cosmica."
        ),
    },
    {
        "key": "ejes_proposito",
        "title": "Ejes de proposito y vocacion",
        "kind": "planets",
        "bodies": ["North Node", "South Node", "Midheaven"],
        "directive": (
            "Analiza el eje Nodo Norte / Nodo Sur (la direccion de "
            "crecimiento versus la zona de confort automatica) y el Medio "
            "Cielo (la imagen publica y vocacional) de esta carta. Conecta "
            "explicitamente esto con lo ya descrito en identidad nuclear: "
            "hacia donde empuja el desarrollo de esta persona."
        ),
    },
    {
        "key": "aspectos",
        "title": "Patrones de aspectos dominantes",
        "kind": "aspects",
        "directive": (
            "Tomando la lista completa de aspectos mayores de esta carta, "
            "identifica y desarrolla los 3 a 5 patrones estructurales mas "
            "relevantes (los de orbe mas ajustado, los que involucran "
            "luminarias o angulos, o los que se repiten formando una figura "
            "-- ej. varios aspectos sobre el mismo planeta). No listes todos "
            "los aspectos uno por uno: identifica el patron que organizan en "
            "conjunto y que dice sobre como esta persona maneja tension "
            "interna versus fluidez."
        ),
    },
    {
        "key": "sintesis",
        "title": "Sintesis final accionable",
        "kind": "synthesis",
        "directive": (
            "Cerra el informe con una sintesis final accionable (aprox. 1 "
            "pagina). No repitas lo ya dicho seccion por seccion -- integra "
            "los patrones centrales de la carta en una lectura unificada de "
            "hacia donde tiende esta personalidad bajo presion y en su mejor "
            "version, y que es lo primero que valdria la pena trabajar. Tiene "
            "que leerse como una conclusion clinica, no como un resumen."
        ),
    },
]
