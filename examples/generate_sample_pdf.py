"""Genera un PDF de ejemplo para revisar el DISEÑO de la Etapa 3 (portada +
páginas de contenido) sin depender de una llamada real a la API.

El texto de las 8 secciones no lo escribió Claude -- lo escribí a mano
siguiendo las mismas reglas de tono de report_engine/config.py
(SYSTEM_TONE_INSTRUCTIONS) y basándome en los placements reales de la carta
de prueba, para que la revisión visual sea representativa de cómo se va a
ver un informe real (densidad de texto, prosa justificada, sin bullets).

Uso:
    python examples/generate_sample_pdf.py

Escribe el PDF en examples/output/informe_ejemplo.pdf.
"""

from pathlib import Path

from natal_engine.chart import generate_natal_chart
from pdf_engine.exporter import generate_pdf

DATOS_DE_PRUEBA = dict(
    name="Mariana Etchegaray",
    date_str="1990-05-14",
    time_str="14:32",
    latitude=-34.6037,
    longitude=-58.3816,
)

SAMPLE_SECTIONS = [
    {
        "key": "introduccion",
        "title": "Introducción operativa",
        "text": (
            "Esta carta tiene una arquitectura clara: seis de los diez cuerpos "
            "principales caen en signos de tierra, y cuatro de ellos -- Luna, "
            "Saturno, Urano y Neptuno -- se agrupan en Capricornio, en las "
            "casas 4 y 5. No es una acumulación decorativa: es el núcleo "
            "organizador de la carta. Vos construís identidad a través de "
            "estructura, y esa estructura se instala primero en el territorio "
            "privado -- familia, raíces, lo que hacés cuando nadie te está "
            "mirando -- antes de mostrarse hacia afuera.\n\n"
            "El resto del informe va a desarrollar esto en capas: primero el "
            "motor de identidad (Sol, Luna, Ascendente), después el estilo "
            "relacional y pulsional, la tensión entre expansión y estructura, "
            "las capas más profundas y generacionales, el eje de propósito, "
            "los patrones de aspectos que más pesan, y una síntesis final. "
            "Cada sección vuelve, de una forma u otra, a la misma pregunta: "
            "qué pasa cuando la necesidad de control choca con lo que no se "
            "puede controlar."
        ),
    },
    {
        "key": "identidad_nuclear",
        "title": "Identidad nuclear: Sol, Luna, Ascendente",
        "text": (
            "El Sol en Tauro, casa 8, ya plantea la primera fricción "
            "funcional de esta carta: la identidad busca terreno fijo y "
            "previsible, pero está ubicada exactamente en la casa de lo que "
            "no es tuyo del todo -- recursos compartidos, procesos de "
            "transformación, lo que se negocia con otros. Integrado, esto "
            "produce una capacidad rara de sostener intensidad ajena sin "
            "quebrarse. No integrado, es la insistencia en controlar "
            "procesos -- duelos, negociaciones, vínculos -- que por "
            "definición no se controlan.\n\n"
            "La Luna en Capricornio, casa 5, regula el mundo emocional "
            "administrándolo: la contención se logra haciéndose cargo, no "
            "pidiendo ayuda, incluso en el terreno que debería ser el más "
            "espontáneo -- el placer, la creatividad, el juego. La sombra "
            "típica es la incapacidad de disfrutar algo sin primero "
            "justificar que se lo ganó.\n\n"
            "El Ascendente en Virgo modera esta combinación hacia afuera: lo "
            "que el entorno percibe primero es precisión, autoexigencia "
            "visible, capacidad de corrección constante. No es una máscara "
            "que oculta al Sol y la Luna -- es una traducción bastante fiel. "
            "El Sol y la Luna están en trígono aplicativo entre sí, lo cual "
            "le da a este núcleo una coherencia interna real: no hay guerra "
            "entre la identidad consciente y el patrón emocional automático, "
            "hay refuerzo mutuo. El costo de esa coherencia es la poca "
            "permeabilidad ante lo que no encaja en el molde tierra-tierra."
        ),
    },
    {
        "key": "estilo_relacional",
        "title": "Estilo cognitivo, relacional y pulsional",
        "text": (
            "Mercurio en Tauro, casa 8 y retrógrado, piensa despacio y hacia "
            "adentro antes de hablar. Que sea retrógrado en esta casa puntual "
            "indica que el procesamiento no es solo lento por temperamento: "
            "es lento porque el material que procesa -- lo intenso, lo no "
            "dicho, lo ajeno -- se revisa varias veces antes de decidir si "
            "se comparte. Cuando por fin lo dice, ya lo pensó de sobra; la "
            "sombra es que a veces lo dice tan tarde que pierde la "
            "oportunidad de discutirlo mientras todavía importaba.\n\n"
            "Venus en Aries, casa 7, quiere iniciativa en el vínculo: elegir, "
            "no esperar a ser elegida. Marte en Piscis, en la misma casa, "
            "hace exactamente lo contrario -- diluye el conflicto en vez de "
            "sostenerlo, cede terreno antes de pelearlo. Tener a Venus y "
            "Marte en la misma casa pero en modos casi opuestos genera una "
            "relación ambivalente con el propio deseo en pareja: sabés lo "
            "que querés con una claridad casi impulsiva (Venus), pero cuando "
            "hay que sostenerlo activamente frente al otro, el impulso se "
            "evapora (Marte). La Luna y Marte forman un sextil prácticamente "
            "exacto: la conexión entre lo que sentís y cómo actuás sobre "
            "eso es rápida y fluida, lo cual hace más notoria la fricción "
            "cuando ese impulso llega a la casa 7 y se disuelve en vez de "
            "sostenerse."
        ),
    },
    {
        "key": "estructura_expansion",
        "title": "Estructura y expansión",
        "text": (
            "Júpiter en Cáncer, casa 10, busca sentido a través de un rol "
            "público con componente de cuidado: la carrera funciona como "
            "extensión del instinto de sostener a otros, no como un "
            "ejercicio de ambición pura. Saturno en Capricornio -- en su "
            "propio signo, retrógrado, casa 5 -- describe una autodisciplina "
            "completamente internalizada: no es una regla que te impusieron, "
            "es una que te impusiste vos misma hace tanto que ya no la "
            "notás como regla. Aplicada al territorio de la casa 5, produce "
            "una relación cautelosa con el riesgo creativo: mostrar algo "
            "propio sin la garantía de que va a salir bien.\n\n"
            "El dato más preciso de esta sección es Júpiter en oposición "
            "casi exacta a Urano -- menos de un cuarto de grado de orbe. "
            "Esta es una de las tensiones estructurales más fuertes de toda "
            "la carta: la búsqueda de expansión y sentido (Júpiter) tira en "
            "dirección opuesta a la necesidad de libertad súbita e "
            "imprevisible (Urano). No se resuelve integrando un extremo y "
            "descartando el otro -- se resuelve aceptando que el crecimiento "
            "real, en esta carta, va a requerir sacudones que no se pueden "
            "planificar con anticipación, por más que el resto de la "
            "estructura pida lo contrario."
        ),
    },
    {
        "key": "capas_profundas",
        "title": "Capas generacionales y profundas",
        "text": (
            "Urano en Capricornio, casa 4, retrógrado, aterriza la necesidad "
            "generacional de ruptura exactamente en el territorio familiar: "
            "el impulso de individuarse de la estructura de origen está ahí, "
            "pero retrógrado y en un signo de tierra tiende a posponerse, a "
            "procesarse puertas adentro antes de traducirse en un cambio "
            "visible. Neptuno, también en Capricornio y casa 5, retrógrado, "
            "introduce una nota de disolución en el mismo territorio donde "
            "Saturno pide disciplina: el límite entre el rigor creativo y el "
            "autoborrado se puede volver difícil de ubicar, sobre todo "
            "cuando el ideal de perfección (Neptuno) se mezcla con la "
            "autoexigencia (Saturno) hasta el punto de no distinguir cuál es "
            "cuál.\n\n"
            "Plutón en Escorpio -- en su propio signo -- casa 2, concentra "
            "toda la intensidad de este planeta en el terreno de los "
            "recursos propios y el valor personal. No es un Plutón diluido "
            "ni genérico: es una relación con la seguridad material y la "
            "autoestima que no admite versiones tibias. Integrado, da una "
            "capacidad notable para reconstruir el propio valor después de "
            "una pérdida real. No integrado, convierte cualquier amenaza a "
            "los recursos o al amor propio en una cuestión de supervivencia, "
            "incluso cuando no lo es."
        ),
    },
    {
        "key": "ejes_proposito",
        "title": "Ejes de propósito y vocación",
        "text": (
            "El Nodo Norte en Acuario, casa 6, marca una dirección de "
            "crecimiento hacia la contribución sistemática y concreta -- "
            "aportar a algo más grande a través del trabajo cotidiano bien "
            "hecho, no a través del gesto individual. El Nodo Sur en Leo, "
            "casa 12, es la zona de confort de la que ese crecimiento se "
            "aleja: la validación privada, casi invisible para otros, "
            "buscada en soledad en vez de puesta a prueba en un sistema "
            "compartido. La carta empuja a salir de ahí.\n\n"
            "El Medio Cielo en Géminis construye una imagen pública basada "
            "en la comunicación, el manejo de información y la versatilidad "
            "-- no en la autoridad vertical de Capricornio ni en el brillo "
            "de Leo. Mercurio forma una cuadratura con el eje nodal: la "
            "forma en que pensás y comunicás no es un dato lateral en este "
            "propósito, es exactamente el terreno donde se juega el "
            "crecimiento. La fricción entre el Mercurio retrógrado e "
            "introspectivo de la casa 8 y la exigencia nodal de comunicar "
            "hacia afuera, en un sistema (casa 6), es probablemente uno de "
            "los nudos vocacionales más concretos de toda la carta."
        ),
    },
    {
        "key": "aspectos",
        "title": "Patrones de aspectos dominantes",
        "text": (
            "Dos aspectos de esta carta tienen un orbe prácticamente exacto "
            "y por eso pesan más que el resto: Júpiter en oposición a Urano "
            "(0.19 grados) y Marte en cuadratura al Medio Cielo (0.11 "
            "grados). El primero ya se desarrolló como la tensión entre "
            "expansión planificada y libertad imprevisible. El segundo "
            "agrega otra capa: la forma en que actuás por impulso (Marte, "
            "diluido en Piscis) entra en fricción directa con la imagen "
            "pública que estás construyendo (Medio Cielo en Géminis). "
            "Cuando la asertividad se posterga demasiado tiempo puertas "
            "adentro, termina saliendo de un modo que no coincide con la "
            "imagen cuidada que se proyecta hacia afuera.\n\n"
            "El segundo patrón notable es estructural, no de un solo "
            "aspecto: el cúmulo de Luna, Saturno y Neptuno en Capricornio, "
            "todos conectados entre sí por conjunción o sextil, confirma que "
            "la carga emocional, la autoexigencia y la idealización no son "
            "tres fuerzas separadas sino una sola máquina bien aceitada -- "
            "para bien y para mal. Por último, tanto Mercurio como Venus "
            "forman aspectos tensos con el eje de los Nodos: la mente y el "
            "deseo están directamente implicados en la dirección de "
            "crecimiento de esta carta, no son observadores de afuera."
        ),
    },
    {
        "key": "sintesis",
        "title": "Síntesis final accionable",
        "text": (
            "Esta carta no tiene un conflicto disperso en muchos frentes: "
            "tiene una sola tensión central que se repite con distintos "
            "disfraces. Del lado de la estructura están el Sol, la Luna, "
            "Saturno y el Ascendente, todos empujando hacia el control, la "
            "previsibilidad y el mérito ganado. Del lado opuesto están "
            "Urano, Neptuno y Marte, empujando hacia lo imprevisible, lo "
            "disuelto y lo que no se puede planificar. Bajo presión, esta "
            "carta tiende a resolver la tensión apretando el lado de la "
            "estructura -- más control, más exigencia, menos margen para el "
            "error -- lo cual funciona a corto plazo y se vuelve agotador a "
            "mediano plazo.\n\n"
            "En su mejor versión, esta personalidad no elimina esa tensión: "
            "la usa. La estructura sostiene lo suficiente como para que la "
            "parte impredecible tenga dónde apoyarse sin volverse caótica. "
            "Lo primero que valdría la pena trabajar es el punto más "
            "concreto donde esto se juega a diario: la casa 7, donde Venus "
            "pide iniciativa clara y Marte la disuelve. Practicar sostener "
            "un desacuerdo o un pedido directo en el vínculo, sin ceder "
            "automáticamente ni sobrecompensar con más control después, es "
            "el ejercicio más chico y más transferible al resto de la "
            "carta."
        ),
    },
]


def build_sample_report():
    return {
        "subject_name": DATOS_DE_PRUEBA["name"],
        "model": None,
        "sections": SAMPLE_SECTIONS,
        "full_text": "",
        "usage": {
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
        },
    }


def main():
    chart = generate_natal_chart(**DATOS_DE_PRUEBA)
    chart["subject"]["place"]["resolved_display_name"] = "Buenos Aires, Argentina"

    report = build_sample_report()

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "informe_ejemplo.pdf"

    generate_pdf(chart, report, str(output_path))
    print(f"PDF de ejemplo generado en {output_path}")


if __name__ == "__main__":
    main()
