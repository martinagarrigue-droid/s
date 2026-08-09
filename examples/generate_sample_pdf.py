"""Genera un PDF de ejemplo para revisar el DISEÑO de la Etapa 3 (portada +
paginas de contenido) sin depender de una llamada real a la API.

El texto de las 8 secciones no lo escribio Claude -- lo escribi a mano
siguiendo las mismas reglas de tono de report_engine/config.py
(SYSTEM_TONE_INSTRUCTIONS) y basandome en los placements reales de la carta
de prueba, para que la revision visual sea representativa de como se va a
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
        "title": "Introduccion operativa",
        "text": (
            "Esta carta tiene una arquitectura clara: seis de los diez cuerpos "
            "principales caen en signos de tierra, y cuatro de ellos -- Luna, "
            "Saturno, Urano y Neptuno -- se agrupan en Capricornio, en las "
            "casas 4 y 5. No es una acumulacion decorativa: es el nucleo "
            "organizador de la carta. Vos construis identidad a traves de "
            "estructura, y esa estructura se instala primero en el territorio "
            "privado -- familia, raices, lo que haces cuando nadie te esta "
            "mirando -- antes de mostrarse hacia afuera.\n\n"
            "El resto del informe va a desarrollar esto en capas: primero el "
            "motor de identidad (Sol, Luna, Ascendente), despues el estilo "
            "relacional y pulsional, la tension entre expansion y estructura, "
            "las capas mas profundas y generacionales, el eje de proposito, "
            "los patrones de aspectos que mas pesan, y una sintesis final. "
            "Cada seccion vuelve, de una forma u otra, a la misma pregunta: "
            "que pasa cuando la necesidad de control choca con lo que no se "
            "puede controlar."
        ),
    },
    {
        "key": "identidad_nuclear",
        "title": "Identidad nuclear: Sol, Luna, Ascendente",
        "text": (
            "El Sol en Tauro, casa 8, ya plantea la primera friccion "
            "funcional de esta carta: la identidad busca terreno fijo y "
            "previsible, pero esta ubicada exactamente en la casa de lo que "
            "no es tuyo del todo -- recursos compartidos, procesos de "
            "transformacion, lo que se negocia con otros. Integrado, esto "
            "produce una capacidad rara de sostener intensidad ajena sin "
            "quebrarse. No integrado, es la insistencia en controlar "
            "procesos -- duelos, negociaciones, vinculos -- que por "
            "definicion no se controlan.\n\n"
            "La Luna en Capricornio, casa 5, regula el mundo emocional "
            "administrandolo: la contencion se logra haciendose cargo, no "
            "pidiendo ayuda, incluso en el terreno que deberia ser el mas "
            "espontaneo -- el placer, la creatividad, el juego. La sombra "
            "tipica es la incapacidad de disfrutar algo sin primero "
            "justificar que se lo gano.\n\n"
            "El Ascendente en Virgo modera esta combinacion hacia afuera: lo "
            "que el entorno percibe primero es precision, autoexigencia "
            "visible, capacidad de correccion constante. No es una mascara "
            "que oculta al Sol y la Luna -- es una traduccion bastante fiel. "
            "El Sol y la Luna estan en trigono aplicativo entre si, lo cual "
            "le da a este nucleo una coherencia interna real: no hay guerra "
            "entre la identidad consciente y el patron emocional automatico, "
            "hay refuerzo mutuo. El costo de esa coherencia es la poca "
            "permeabilidad ante lo que no encaja en el molde tierra-tierra."
        ),
    },
    {
        "key": "estilo_relacional",
        "title": "Estilo cognitivo, relacional y pulsional",
        "text": (
            "Mercurio en Tauro, casa 8 y retrogrado, piensa despacio y hacia "
            "adentro antes de hablar. La retrogradacion en esta casa "
            "especifica que el procesamiento no es solo lento por "
            "temperamento: es lento porque el material que procesa -- lo "
            "intenso, lo no dicho, lo ajeno -- se revisa varias veces antes "
            "de decidir si se comparte. Cuando por fin lo dice, ya lo penso "
            "de sobra; la sombra es que a veces lo dice tan tarde que pierde "
            "la oportunidad de discutirlo mientras todavia importaba.\n\n"
            "Venus en Aries, casa 7, quiere iniciativa en el vinculo: elegir, "
            "no esperar a ser elegida. Marte en Piscis, en la misma casa, "
            "hace exactamente lo contrario -- diluye el conflicto en vez de "
            "sostenerlo, cede terreno antes de pelearlo. Tener a Venus y "
            "Marte en la misma casa pero en modos casi opuestos genera una "
            "relacion ambivalente con el propio deseo en pareja: sabes lo "
            "que queres con una claridad casi impulsiva (Venus), pero cuando "
            "hay que sostenerlo activamente frente al otro, el impulso se "
            "evapora (Marte). La Luna y Marte forman un sextil practicamente "
            "exacto: la conexion entre lo que sentis y como actuas sobre "
            "eso es rapida y fluida, lo cual hace mas notoria la friccion "
            "cuando ese impulso llega a la casa 7 y se disuelve en vez de "
            "sostenerse."
        ),
    },
    {
        "key": "estructura_expansion",
        "title": "Estructura y expansion",
        "text": (
            "Jupiter en Cancer, casa 10, busca sentido a traves de un rol "
            "publico con componente de cuidado: la carrera funciona como "
            "extension del instinto de sostener a otros, no como un "
            "ejercicio de ambicion pura. Saturno en Capricornio -- en su "
            "propio signo, retrogrado, casa 5 -- describe una autodisciplina "
            "completamente internalizada: no es una regla que te impusieron, "
            "es una que te impusiste vos misma hace tanto que ya no la "
            "notas como regla. Aplicada al territorio de la casa 5, produce "
            "una relacion cautelosa con el riesgo creativo: mostrar algo "
            "propio sin la garantia de que va a salir bien.\n\n"
            "El dato mas preciso de esta seccion es Jupiter en oposicion "
            "casi exacta a Urano -- menos de un cuarto de grado de orbe. "
            "Esta es una de las tensiones estructurales mas fuertes de toda "
            "la carta: la busqueda de expansion y sentido (Jupiter) tira en "
            "direccion opuesta a la necesidad de libertad subita e "
            "imprevisible (Urano). No se resuelve integrando un extremo y "
            "descartando el otro -- se resuelve aceptando que el crecimiento "
            "real, en esta carta, va a requerir sacudones que no se pueden "
            "planificar con anticipacion, por mas que el resto de la "
            "estructura pida lo contrario."
        ),
    },
    {
        "key": "capas_profundas",
        "title": "Capas generacionales y profundas",
        "text": (
            "Urano en Capricornio, casa 4, retrogrado, aterriza la necesidad "
            "generacional de ruptura exactamente en el territorio familiar: "
            "el impulso de individuarse de la estructura de origen esta ahi, "
            "pero retrogrado y en un signo de tierra tiende a posponerse, a "
            "procesarse puertas adentro antes de traducirse en un cambio "
            "visible. Neptuno, tambien en Capricornio y casa 5, retrogrado, "
            "introduce una nota de disolucion en el mismo territorio donde "
            "Saturno pide disciplina: el limite entre el rigor creativo y el "
            "autoborrado se puede volver dificil de ubicar, sobre todo "
            "cuando el ideal de perfeccion (Neptuno) se mezcla con la "
            "autoexigencia (Saturno) hasta el punto de no distinguir cual es "
            "cual.\n\n"
            "Pluton en Escorpio -- en su propio signo -- casa 2, concentra "
            "toda la intensidad de este planeta en el terreno de los "
            "recursos propios y el valor personal. No es un Pluton diluido "
            "ni generico: es una relacion con la seguridad material y la "
            "autoestima que no admite versiones tibias. Integrado, da una "
            "capacidad notable para reconstruir el propio valor despues de "
            "una perdida real. No integrado, convierte cualquier amenaza a "
            "los recursos o al amor propio en una cuestion de supervivencia, "
            "incluso cuando no lo es."
        ),
    },
    {
        "key": "ejes_proposito",
        "title": "Ejes de proposito y vocacion",
        "text": (
            "El Nodo Norte en Acuario, casa 6, marca una direccion de "
            "crecimiento hacia la contribucion sistematica y concreta -- "
            "aportar a algo mas grande a traves del trabajo cotidiano bien "
            "hecho, no a traves del gesto individual. El Nodo Sur en Leo, "
            "casa 12, es la zona de confort de la que ese crecimiento se "
            "aleja: la validacion privada, casi invisible para otros, "
            "buscada en soledad en vez de puesta a prueba en un sistema "
            "compartido. La carta empuja a salir de ahi.\n\n"
            "El Medio Cielo en Geminis construye una imagen publica basada "
            "en la comunicacion, el manejo de informacion y la versatilidad "
            "-- no en la autoridad vertical de Capricornio ni en el brillo "
            "de Leo. Mercurio forma una cuadratura con el eje nodal: la "
            "forma en que pensas y comunicas no es un dato lateral en este "
            "proposito, es exactamente el terreno donde se juega el "
            "crecimiento. La friccion entre el Mercurio retrogrado e "
            "introspectivo de la casa 8 y la exigencia nodal de comunicar "
            "hacia afuera, en un sistema (casa 6), es probablemente uno de "
            "los nudos vocacionales mas concretos de toda la carta."
        ),
    },
    {
        "key": "aspectos",
        "title": "Patrones de aspectos dominantes",
        "text": (
            "Dos aspectos de esta carta tienen un orbe practicamente exacto "
            "y por eso pesan mas que el resto: Jupiter en oposicion a Urano "
            "(0.19 grados) y Marte en cuadratura al Medio Cielo (0.11 "
            "grados). El primero ya se desarrollo como la tension entre "
            "expansion planificada y libertad imprevisible. El segundo "
            "agrega otra capa: la forma en que actuas por impulso (Marte, "
            "diluido en Piscis) entra en friccion directa con la imagen "
            "publica que estas construyendo (Medio Cielo en Geminis). "
            "Cuando la asertividad se posterga demasiado tiempo puertas "
            "adentro, termina saliendo de un modo que no coincide con la "
            "imagen cuidada que se proyecta hacia afuera.\n\n"
            "El segundo patron notable es estructural, no de un solo "
            "aspecto: el cumulo de Luna, Saturno y Neptuno en Capricornio, "
            "todos conectados entre si por conjuncion o sextil, confirma que "
            "la carga emocional, la autoexigencia y la idealizacion no son "
            "tres fuerzas separadas sino una sola maquina bien aceitada -- "
            "para bien y para mal. Por ultimo, tanto Mercurio como Venus "
            "forman aspectos tensos con el eje de los Nodos: la mente y el "
            "deseo estan directamente implicados en la direccion de "
            "crecimiento de esta carta, no son observadores de afuera."
        ),
    },
    {
        "key": "sintesis",
        "title": "Sintesis final accionable",
        "text": (
            "Esta carta no tiene un conflicto disperso en muchos frentes: "
            "tiene una sola tension central que se repite con distintos "
            "disfraces. Del lado de la estructura estan el Sol, la Luna, "
            "Saturno y el Ascendente, todos empujando hacia el control, la "
            "previsibilidad y el merito ganado. Del lado opuesto estan "
            "Urano, Neptuno y Marte, empujando hacia lo imprevisible, lo "
            "disuelto y lo que no se puede planificar. Bajo presion, esta "
            "carta tiende a resolver la tension apretando el lado de la "
            "estructura -- mas control, mas exigencia, menos margen para el "
            "error -- lo cual funciona a corto plazo y se vuelve agotador a "
            "mediano plazo.\n\n"
            "En su mejor version, esta personalidad no elimina esa tension: "
            "la usa. La estructura sostiene lo suficiente como para que la "
            "parte impredecible tenga donde apoyarse sin volverse caotica. "
            "Lo primero que valdria la pena trabajar es el punto mas "
            "concreto donde esto se juega a diario: la casa 7, donde Venus "
            "pide iniciativa clara y Marte la disuelve. Practicar sostener "
            "un desacuerdo o un pedido directo en el vinculo, sin ceder "
            "automaticamente ni sobrecompensar con mas control despues, es "
            "el ejercicio mas chico y mas transferible a el resto de la "
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
