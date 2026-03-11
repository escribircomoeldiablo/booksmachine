from __future__ import annotations

import re
from typing import Any


PROCEDURE_EVIDENCE_FIELDS: tuple[str, ...] = (
    "procedure_steps",
    "decision_rules",
    "preconditions",
    "exceptions",
    "author_variants",
    "procedure_outputs",
)

_FRAME_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "determine_predominator",
        "frame_type": "selection",
        "label": "Determine Predominator",
        "goal": "Determine which factor holds the predomination in the nativity.",
        "anchor_concepts": ("predominator",),
        "supporting_concepts": (
            "predomination",
            "predomination of light",
            "predomination of sect light",
            "sect light predomination criteria",
            "sect light preference",
            "positional consideration for selecting predominator",
            "angularity in predomination",
        ),
        "related_concepts": ("sect", "house system", "oikodespotes"),
        "include_signals": (
            "predominator",
            "predomination",
            "sect light",
            "candidate",
            "ascendant",
            "lot of fortune",
            "prenatal lunation",
            "witnessed",
        ),
        "exclude_signals": (
            "good character",
            "success by means",
            "illness",
            "fortunate and unfortunate experiences",
        ),
    },
    {
        "id": "apply_profections",
        "frame_type": "timing",
        "label": "Apply Profections",
        "goal": "Apply profections to determine the time lord and the matters emphasized during the profected period.",
        "anchor_concepts": ("profection", "annual lord of year", "time lord"),
        "supporting_concepts": ("chronokrator",),
        "related_concepts": ("primary directions", "progressions"),
        "include_signals": (
            "profection",
            "annual lord",
            "time lord",
            "chronokrator",
            "profected sign",
            "activated",
            "zodiacal order",
            "period of influence",
        ),
        "exclude_signals": (
            "circumambulation",
            "primary directions",
            "progressions",
        ),
    },
    {
        "id": "determine_oikodespotes",
        "frame_type": "selection",
        "label": "Determine Oikodespotes",
        "goal": "Determine the master of the nativity by selecting the appropriate ruler from the Predominator or other designated source.",
        "anchor_concepts": ("oikodespotes", "master of the nativity"),
        "supporting_concepts": ("sunoikodespotes joint master",),
        "related_concepts": ("predominator", "house system"),
        "include_signals": (
            "oikodespotes",
            "master of the nativity",
            "bound lord",
            "domicile lord",
            "joint master",
            "sunoikodespotes",
            "witnessed by the predominator",
            "assign",
            "determine",
            "select",
        ),
        "exclude_signals": (
            "good character",
            "success by means",
            "what it signifies",
            "character delineation",
            "physical constitution",
            "harm",
            "ill repute",
        ),
    },
    {
        "id": "determine_kurios",
        "frame_type": "selection",
        "label": "Determine Kurios",
        "goal": "Determine the Lord of the Nativity by evaluating the authoritative planetary candidates and selecting the strongest one.",
        "anchor_concepts": ("kurio", "lord of the nativity"),
        "supporting_concepts": ("almuten", "almuten al mubtazz"),
        "related_concepts": ("predominator", "midheaven", "lot of fortune", "sect"),
        "include_signals": (
            "kurios",
            "lord of the nativity",
            "almuten",
            "victor",
            "authoritative",
            "midheaven",
            "heliacal",
            "candidate",
            "select",
            "disqualified",
        ),
        "exclude_signals": (
            "oikodespotes",
            "master of the nativity",
            "zodiacal releasing",
            "lot of fortune the first house",
        ),
    },
    {
        "id": "analyze_lot_of_fortune",
        "frame_type": "analysis",
        "label": "Analyze Lot of Fortune",
        "goal": "Calculate and interpret the Lot of Fortune, its ruler, derived Fortune houses, and releasing periods.",
        "anchor_concepts": ("lot of fortune",),
        "supporting_concepts": ("fortune house", "releasing house"),
        "related_concepts": ("derived houses", "sect", "predominator"),
        "include_signals": (
            "lot of fortune",
            "fortune houses",
            "zodiacal releasing",
            "witness the lot",
            "material prosperity",
            "bodily well being",
            "diurnal",
            "nocturnal",
        ),
        "exclude_signals": (
            "kurios",
            "oikodespotes",
            "master of the nativity",
        ),
    },
    {
        "id": "assess_sect_light",
        "frame_type": "selection",
        "label": "Assess Sect Light",
        "goal": "Identify the sect light and determine whether it qualifies as predominator or whether the contrary light must be examined.",
        "anchor_concepts": ("sect light", "sect"),
        "supporting_concepts": (),
        "related_concepts": ("predominator", "lot of fortune", "releasing house"),
        "include_signals": (
            "sect light",
            "predominator",
            "contrary light",
            "angular",
            "succedent",
            "cadent",
            "releasing house",
            "valid house",
        ),
        "exclude_signals": (
            "oikodespotes",
            "kurios",
            "lot of fortune the first house",
        ),
    },
    {
        "id": "derive_houses",
        "frame_type": "analysis",
        "label": "Derive Houses",
        "goal": "Derive a house from a reference house and interpret its condition for the target person or topic.",
        "anchor_concepts": ("derived houses",),
        "supporting_concepts": (),
        "related_concepts": ("lot of fortune", "fortune house"),
        "include_signals": (
            "derived house",
            "count forward",
            "reference house",
            "condition",
            "question at hand",
        ),
        "exclude_signals": (
            "kurios",
            "oikodespotes",
            "sect light",
        ),
    },
    {
        "id": "assess_aversion",
        "frame_type": "analysis",
        "label": "Assess Aversion",
        "goal": "Determine whether a lord is in aversion to the Ascendant and interpret the resulting obstacles or difficulties in steering life topics.",
        "anchor_concepts": ("aversion",),
        "supporting_concepts": (),
        "related_concepts": ("domicile lord of ascendant", "derived houses", "predominator"),
        "include_signals": (
            "aversion",
            "whole sign aspect",
            "ascendant",
            "steering is difficult",
            "challenging topics",
            "lord is in house",
        ),
        "exclude_signals": (
            "oikodespotes",
            "kurios",
            "lot of fortune",
        ),
    },
    {
        "id": "evaluate_domicile_lord_of_ascendant",
        "frame_type": "evaluation",
        "label": "Evaluate Domicile Lord of Ascendant",
        "goal": "Evaluate the condition of the domicile lord of the Ascendant and its capacity to steer the native's life.",
        "anchor_concepts": ("domicile lord of ascendant",),
        "supporting_concepts": (),
        "related_concepts": ("ascendant", "aversion", "predominator"),
        "include_signals": (
            "domicile lord of ascendant",
            "self steering",
            "direct life",
            "first house",
            "good condition",
            "native is strong",
        ),
        "exclude_signals": (
            "oikodespotes",
            "kurios",
        ),
    },
    {
        "id": "identify_apheta_hyleg",
        "frame_type": "selection",
        "label": "Identify Apheta Hyleg",
        "goal": "Identify the Predominator in its longevity role as apheta or hyleg for assigning the oikodespotes and continuing the life-length procedure.",
        "anchor_concepts": ("predominator apheta hyleg",),
        "supporting_concepts": ("hyleg",),
        "related_concepts": ("predominator", "oikodespotes", "primary directions"),
        "include_signals": (
            "apheta",
            "hyleg",
            "predominator",
            "longevity",
            "releaser",
            "oikodespotes",
        ),
        "exclude_signals": (
            "equal house system",
            "derived house",
        ),
    },
    {
        "id": "evaluate_oikodespotes",
        "frame_type": "evaluation",
        "label": "Evaluate Oikodespotes",
        "goal": "Judge the condition and effects of the Oikodespotes once selected.",
        "anchor_concepts": ("oikodespotes", "master of the nativity"),
        "supporting_concepts": ("sunoikodespotes joint master",),
        "related_concepts": ("predominator",),
        "include_signals": (
            "good character",
            "bad character",
            "good effects",
            "injurious",
            "success by means",
            "what it signifies",
            "physical constitution",
            "bodily constitution",
            "ill repute",
            "harm",
            "benefic",
            "malefic",
            "sect",
            "dignity",
            "angular",
            "succedent",
            "cadent",
        ),
        "exclude_signals": (
            "assign the master",
            "determine the master",
            "domicile lord of the predominator",
            "bound lord of the predominator",
        ),
    },
)

_FRAME_LABELS_ES: dict[str, str] = {
    "determine_predominator": "Determinar predominador",
    "apply_profections": "Aplicar profecciones",
    "determine_oikodespotes": "Determinar oikodespotes",
    "determine_kurios": "Determinar kurios",
    "analyze_lot_of_fortune": "Analizar lote de la fortuna",
    "assess_sect_light": "Evaluar luz de la secta",
    "derive_houses": "Derivar casas",
    "assess_aversion": "Evaluar aversión",
    "evaluate_domicile_lord_of_ascendant": "Evaluar regente domiciliario del ascendente",
    "identify_apheta_hyleg": "Identificar apheta hyleg",
    "evaluate_oikodespotes": "Evaluar oikodespotes",
}

_FRAME_GOALS_ES: dict[str, str] = {
    "determine_predominator": "Determinar qué factor tiene la predominancia en la natividad.",
    "apply_profections": "Aplicar profecciones para determinar el cronocrátor y los temas activados durante el periodo profectado.",
    "determine_oikodespotes": "Determinar el oikodespotes seleccionando el regente apropiado a partir del predominador u otra fuente designada.",
    "determine_kurios": "Determinar el kurios evaluando los candidatos planetarios de autoridad y seleccionando el más fuerte.",
    "analyze_lot_of_fortune": "Calcular e interpretar el Lote de la Fortuna, su regente, las casas derivadas de Fortuna y los periodos de liberación zodiacal.",
    "assess_sect_light": "Identificar la luz de la secta y determinar si califica como predominador o si debe examinarse la luminaria contraria.",
    "derive_houses": "Derivar una casa a partir de una casa de referencia e interpretar su condición para la persona o asunto consultado.",
    "assess_aversion": "Determinar si un regente está en aversión al Ascendente e interpretar los obstáculos o dificultades resultantes en la conducción de los temas de vida.",
    "evaluate_domicile_lord_of_ascendant": "Evaluar la condición del regente domiciliario del Ascendente y su capacidad para dirigir la vida del nativo.",
    "identify_apheta_hyleg": "Identificar el predominador en su función de apheta o hyleg para asignar el oikodespotes y continuar el procedimiento de longevidad.",
    "evaluate_oikodespotes": "Evaluar la condición y los efectos del oikodespotes una vez seleccionado.",
}

_TEXT_ES: dict[str, str] = {
    "Select the type of profection (annual, monthly, daily) according to the timing interval required": "Seleccionar el tipo de profección (anual, mensual o diaria) según el intervalo temporal requerido",
    "Activate each zodiac sign individually in zodiacal order at a fixed rate (annually, monthly, or daily)": "Activar cada signo zodiacal individualmente en orden zodiacal a una cadencia fija (anual, mensual o diaria)",
    "Activate the next sign in zodiacal order at each interval": "Activar el siguiente signo en orden zodiacal en cada intervalo",
    "Identify the house matters occupied by the profected sign": "Identificar los asuntos de la casa ocupada por el signo profectado",
    "Emphasize the matters of the house occupied by the profected sign for that period": "Enfatizar los asuntos de la casa ocupada por el signo profectado durante ese periodo",
    "Determine the planet ruling the profected sign (the time lord)": "Identificar el planeta que rige el signo profectado (el cronocrátor)",
    "Identify the planet that rules the profected sign (the time lord)": "Identificar el planeta que rige el signo profectado (el cronocrátor)",
    "Understand that the time lord governs the life and influences outcomes for the duration of the profection": "Entender que el cronocrátor gobierna la vida e influye en los resultados durante la duración de la profección",
    "Interpret the effect of the time lord during its period of influence based on its significations in the natal chart": "Interpretar el efecto del cronocrátor durante su periodo de influencia según sus significaciones en la carta natal",
    "The time lord who governs the period defined by the profection.": "El cronocrátor que gobierna el periodo definido por la profección.",
    "Identification of the time lord who governs the native's life during the profection period": "Identificación del cronocrátor que gobierna la vida del nativo durante el periodo profectado",
    "Identification of the Predominator planet or point in the natal chart.": "Identificación del planeta o punto predominador en la carta natal.",
    "Timing points from primary directions when planets or points encounter exact aspects or angles": "Momentos de activación en direcciones primarias cuando planetas o puntos alcanzan aspectos exactos o ángulos",
    "Comparison of progressed planetary/angle positions to natal positions to indicate timing of events": "Comparación de posiciones progresadas de planetas y ángulos con posiciones natales para indicar el momento de los eventos",
    "If the light of the sect is cadent, then predomination might go to the other light": "Si la luz de la secta está cadente, la predominancia puede pasar a la otra luminaria",
    "If the Moon is ascending in the east, then the Moon will be the Predominator": "Si la Luna asciende por el este, la Luna es el predominador",
    "If both lights are declining in cadent houses, then predomination goes to the Ascendant": "Si ambas luminarias declinan en casas cadentes, la predominancia pasa al Ascendente",
    "If the Sun is witnessed by its bound lord within own bounds, stop; the Sun is the Predominator": "Si el Sol es testificado por su bound lord dentro de sus propios límites, detenerse; el Sol es el predominador",
    "If witnessed by any of these lords, stop; the Sun is the Predominator": "Si es testificado por cualquiera de estos regentes, detenerse; el Sol es el predominador",
    "For the Moon as possible Predominator (night chart), check if it is in houses 1, 10, or 11": "Para la Luna como posible predominador (carta nocturna), verificar si está en las casas 1, 10 u 11",
    "If witnessed by bound lord, stop; the Moon is the Predominator": "Si es testificada por el bound lord, detenerse; la Luna es el predominador",
    "If witnessed, stop; the Moon is the Predominator": "Si es testificada, detenerse; la Luna es el predominador",
    "If yes, Lot of Fortune is Predominator": "Si la respuesta es sí, el Lote de la Fortuna es el predominador",
    "If Prenatal Lunation is in angular houses and witnessed properly, qualifies as Predominator": "Si la lunación prenatal está en casas angulares y recibe testimonio adecuado, califica como predominador",
    "If the Ascendant is witnessed by its lords, it is the Predominator": "Si el Ascendente es testificado por sus regentes, es el predominador",
    "If the Ascendant is not witnessed by any of its lords, there is no Predominator": "Si el Ascendente no es testificado por ninguno de sus regentes, no hay predominador",
    "Sun in 1st, 10th, or 11th houses AND witnessed by bound lord within bounds": "Sol en casas 1, 10 u 11 Y testificado por el bound lord dentro de los límites",
    "Sun in 1st, 10th, or 11th houses AND not witnessed by bound lord within bounds BUT witnessed by triplicity, domicile, or exaltation lord by whole-sign": "Sol en casas 1, 10 u 11 Y no testificado por el bound lord dentro de los límites, PERO sí por el regente de triplicidad, domicilio o exaltación por signo entero",
    "Moon in 1st, 10th, or 11th houses AND witnessed by bound lord within bounds": "Luna en casas 1, 10 u 11 Y testificada por el bound lord dentro de los límites",
    "Moon in 1st, 10th, or 11th houses AND not witnessed by bound lord BUT witnessed by triplicity, domicile, or exaltation lord by whole-sign": "Luna en casas 1, 10 u 11 Y no testificada por el bound lord, PERO sí por el regente de triplicidad, domicilio o exaltación por signo entero",
    "Lot of Fortune in 1, 10, or 11 houses AND witnessed properly": "Lote de la Fortuna en casas 1, 10 u 11 Y testificado adecuadamente",
    "Prenatal Lunation in 1, 10, or 11 houses AND witnessed properly": "Lunación prenatal en casas 1, 10 u 11 Y testificada adecuadamente",
    "None qualify": "Ninguno califica",
    "none qualify": "Ninguno califica",
    "Default to Ascendant if witnessed, else no Predominator": "Pasar al Ascendente si recibe testimonio; en caso contrario, no hay predominador",
    "default to the Ascendant; the Ascendant must be witnessed by any of its lords to qualify, otherwise no Predominator is declared": "Pasar al Ascendente; el Ascendente debe ser testificado por cualquiera de sus regentes para calificar; de lo contrario, no se declara predominador",
    "Sun is Predominator": "El Sol es el predominador",
    "Moon is Predominator": "La Luna es el predominador",
    "Lot of Fortune is Predominator": "El Lote de la Fortuna es el predominador",
    "Prenatal Lunation is Predominator": "La lunación prenatal es el predominador",
    "Predomination defaults to Ascendant": "La predominancia pasa al Ascendente",
    "Sun will be the Predominator": "El Sol es el predominador",
    "Moon is the Predominator because she is the light of the sect": "La Luna es el predominador porque es la luz de la secta",
    "Ascendant is the Predominator": "El Ascendente es el predominador",
    "predomination goes to the Ascendant": "la predominancia pasa al Ascendente",
    "If Lot of Fortune qualifies, it is Predominator": "Si el Lote de la Fortuna califica, es el predominador",
    "If Ascendant witnessed by any of its lords, Ascendant is Predominator": "Si el Ascendente es testificado por cualquiera de sus regentes, el Ascendente es el predominador",
    "There is no Predominator": "No hay predominador",
    "Sect light is Predominator": "La luz de la secta es el predominador",
    "Disqualify sect light; examine contrary sect light": "Descartar la luz de la secta; examinar la luminaria contraria a la secta",
    "Assign predomination to Ascendant": "Asignar la predominancia al Ascendente",
    "predomination may go to the other light if it satisfies the criteria": "la predominancia puede pasar a la otra luminaria si cumple los criterios",
    "light contrary to the sect is examined": "se examina la luminaria contraria a la secta",
    "predomination defaults to the Ascendant": "la predominancia pasa al Ascendente",
    "Identify the Master of the Nativity (Oikodespotes) as per Porphyry's and other astrologers' procedure": "Identificar el oikodespotes según el procedimiento de Porfirio y otros astrólogos",
    "Determine the Master of the Nativity (Oikodespotes) as the domicile lord of the Predominator according to Porphyry’s main method": "Determinar el oikodespotes como el regente domiciliario del predominador según el método principal de Porfirio",
    "Identify the Master of the Nativity as the first lord witnessing the Predominator": "Identificar el oikodespotes como el primer regente que testifica al predominador",
    "Check if the Master (Oikodespotes) witnesses the Ascendant or the Moon": "Verificar si el oikodespotes testifica al Ascendente o a la Luna",
    "Identification of Master of the Nativity (Oikodespotes) indicating longevity.": "Identificación del oikodespotes como indicador de longevidad.",
    "Identification of the Oikodespotes planet or point in the natal chart.": "Identificación del oikodespotes en la carta natal.",
    "Identification of the Oikodespotes (Master of the Nativity) for the natal chart.": "Identificación del oikodespotes para la carta natal.",
    "Prefers Moon as strongest light by night; rejects Jupiter as Master if in aversion to Moon; may conclude no Oikodespotes present": "Prefiere a la Luna como luminaria más fuerte de noche; rechaza a Júpiter como oikodespotes si está en aversión a la Luna; puede concluir que no hay oikodespotes",
    "Uses Ascendant as Predominator; domicile lord (Sun) confirms it by aspect; does not clearly assign Oikodespotes": "Usa el Ascendente como predominador; el regente domiciliario (Sol) lo confirma por aspecto; no asigna con claridad un oikodespotes",
    "Assigns Saturn as Oikodespotes, domicile lord of Capricorn, following Sagittarius Moon": "Asigna a Saturno como oikodespotes, regente domiciliario de Capricornio, siguiendo a la Luna en Sagitario",
    "Porphyry uniquely identifies both the Master of the Nativity (Oikodespotes) and a second ruler, the Lord of the Nativity (Kurios), using combined criteria including zodiacal rulership and angularity.": "Porfirio identifica de manera singular tanto el oikodespotes como un segundo regente, el kurios, usando criterios combinados que incluyen regencia zodiacal y angularidad.",
    "Designated both Master and Joint-Master of the Nativity; no specific timing procedures for length of life disclosed; noted quality of lifespans based on location of ruler to angles: Ascendant (first age), Midheaven (middle age), Descendant to IC (later age).": "Designó tanto un maestro como un co-maestro de la natividad; no expuso procedimientos temporales específicos para la duración de la vida; señaló la cualidad de la longevidad según la ubicación del regente respecto de los ángulos: Ascendente (primera edad), Medio Cielo (edad media), Descendente al IC (edad tardía).",
    "Jupiter is the Joint-Master of the Nativity (Sunoikodespotes) because it is the bound lord of the Sun (Predominator). Porphyry did not include sect status as a criterion for the Kurios.": "Júpiter es el co-maestro de la natividad (Sunoikodespotes) porque es el regente de límites del Sol (predominador). Porfirio no incluyó el estado de secta como criterio para el kurios.",
    "the Oikodespotes is impeded by malefics or deserted by benefics": "el Oikodespotes está impedido por maléficos o abandonado por benéficos",
    "its efficacy is debilitated with negative indications": "su eficacia se debilita con indicaciones negativas",
    "the Oikodespotes witnesses the Ascendant or the Moon": "el Oikodespotes testifica al Ascendente o a la Luna",
    "There is a connection between the planet that designates the years of life and the physical body": "hay una conexión entre el planeta que designa los años de vida y el cuerpo físico",
    "the Oikodespotes does not belong to the sect of chart, or is combust, under malefic influence, or poorly placed": "el Oikodespotes no pertenece a la secta de la carta, o está combusto, bajo influencia maléfica o mal posicionado",
    "Its beneficial influence and affections are diminished": "su influencia benéfica y sus efectos quedan disminuidos",
    "Jupiter is in aversion to the Moon (the sect light) as per Valens’ method": "Júpiter está en aversión a la Luna (la luz de la secta) según el método de Valens",
    "Reject Jupiter as Master and conclude the nativity lacks an Oikodespotes": "rechazar a Júpiter como Master y concluir que la natividad carece de Oikodespotes",
    "the Oikodespotes possesses the entirety of the nativity and the rulership of individual stars": "el Oikodespotes posee la totalidad de la natividad y el gobierno de las estrellas individuales",
    "and is well posited in its domiciles, exaltation, or signs of joy, and belongs to the sect of the nativity, and is free from harmful malefic aspects and protected by benefics, it indicates all good things and full lifespan": "y está bien posicionado en sus domicilios, exaltación o signos de gozo, pertenece a la secta de la natividad, está libre de aspectos maléficos dañinos y protegido por benéficos, indica todos los bienes y una vida completa",
    "the Master (Oikodespotes) and Joint-Master witness each other by aspect": "el Master (Oikodespotes) y el Joint-Master se testifican mutuamente por aspecto",
    "They are working together harmoniously for the individual": "trabajan juntos armónicamente para el individuo",
    "The nativity lacks an Oikodespotes (according to Valens)": "La natividad carece de oikodespotes (según Valens)",
    "There is no qualified Predominator and thus no Oikodespotes": "No hay predominador calificado y, por tanto, no hay oikodespotes",
    "Reject it as Oikodespotes or continue search for another candidate": "Rechazarlo como oikodespotes o continuar la búsqueda de otro candidato",
    "Its benefic qualities and power are diminished as Oikodespotes": "Sus cualidades benéficas y su poder se ven disminuidos como oikodespotes",
    "Identify and list all candidates for the role of Kurios by evaluating the seven authoritative offices: Lord of the Ascendant, Planet in domicile and bounds of Ascendant, Lord of the Moon, Lord of the Midheaven, Lord of Fortune, Planet making heliacal rise/set/station within seven days of birth, and Bound lord of the Prenatal Lunation": "Identificar y listar todos los candidatos al papel de kurios evaluando los siete cargos de autoridad: regente del Ascendente, planeta en domicilio y límites del Ascendente, regente de la Luna, regente del Medio Cielo, regente de la Fortuna, planeta con salida, puesta o estación helíaca dentro de los siete días del nacimiento, y regente de límites de la lunación prenatal",
    "Identify the lord of the Midheaven. If it is in an angular house, it is the Kurios": "Identificar el regente del Medio Cielo. Si está en una casa angular, es el kurios",
    "If not, seek a planet actually present upon the Midheaven; assign as Kurios": "Si no, buscar un planeta realmente presente sobre el Medio Cielo; asignarlo como kurios",
    "If not, seek a planet ascending towards the Midheaven (e.g., in the eleventh house); assign as Kurios": "Si no, buscar un planeta que ascienda hacia el Medio Cielo (por ejemplo, en la casa undécima); asignarlo como kurios",
    "Identify the seven authoritative planetary candidates: lord of the Ascendant, planet in domicile and bounds of Ascendant, lord of the Moon, lord of the Midheaven, lord of Fortune, planet making heliacal rise/set/station within seven days before/after birth (give preference to the one rising and visible), bound lord of Prenatal Lunation (New Moon if natal Moon waxing, Full Moon if waning)": "Identificar los siete candidatos planetarios de autoridad: regente del Ascendente, planeta en domicilio y límites del Ascendente, regente de la Luna, regente del Medio Cielo, regente de la Fortuna, planeta con salida, puesta o estación helíaca dentro de los siete días antes o después del nacimiento (preferir el que asciende y es visible), y regente de límites de la lunación prenatal (Luna Nueva si la Luna natal está creciente, Luna Llena si está menguante)",
    "If none of the candidates are in especially strong condition, select the least problematic as Kurios, recognizing its limitations": "Si ninguno de los candidatos está en condición especialmente fuerte, seleccionar el menos problemático como kurios, reconociendo sus limitaciones",
    "Evaluate each candidate according to: 1) greatest sympathy with the nativity; 2) placement in front; 3) being more eastern; 4) being more in its own familiar places (domicile, exaltation, triplicity, bounds); 5) greatest strength in relation to the figure of the nativity and co-witnessing by other planets": "Evaluar cada candidato según: 1) mayor simpatía con la natividad; 2) ubicación al frente; 3) ser más oriental; 4) estar más en sus lugares propios y familiares (domicilio, exaltación, triplicidad, límites); 5) mayor fuerza en relación con la figura de la natividad y co-testimonio de otros planetas",
    "Proclaim as Kurios the planet found to be most aligned by these criteria": "Proclamar como kurios el planeta que resulte más alineado según estos criterios",
    "It is selected as Kurios.": "Se selecciona como kurios",
    "Prefer the planet that is rising and more visible.": "Preferir el planeta que asciende y es más visible",
    "It is disqualified except according to Ptolemy.": "Queda descalificado, excepto según Ptolomeo",
    "it is disqualified from being Kurios by most authorities": "queda descalificado como kurios según la mayoría de las autoridades",
    "Select the candidate higher in Porphyry’s order of offices.": "Seleccionar el candidato más alto en el orden de cargos de Porfirio",
    "Kurios may be a weak or ineffective leader": "el kurios puede ser un regente débil o ineficaz",
    "Identification of the planetary Kurios, Lord of the Nativity.": "Identificación del kurios planetario, regente de la natividad.",
    "A single planet determined as Kurios, the most qualified guiding authority over the nativity.": "Un único planeta determinado como kurios, la autoridad rectora más calificada sobre la natividad.",
    "Calculate the Lot of Fortune based on whether the chart is diurnal (Sun to Moon) or nocturnal (Moon to Sun)": "Calcular el Lote de la Fortuna según si la carta es diurna (del Sol a la Luna) o nocturna (de la Luna al Sol)",
    "Locate the Lot of Fortune in the zodiac and determine its sign and house": "Localizar el Lote de la Fortuna en el zodiaco y determinar su signo y casa",
    "Assess the house strength (angular, succedent, cadent) and favorability of the Lot of Fortune’s position": "Evaluar la fuerza de la casa (angular, sucedente, cadente) y la favorabilidad de la posición del Lote de la Fortuna",
    "Determine which planets witness the Lot of Fortune (benefics or malefics; via aspect or co-presence)": "Determinar qué planetas testifican al Lote de la Fortuna (benéficos o maléficos; por aspecto o copresencia)",
    "Assess the dignity of the sign ruler of the Lot of Fortune (domicile, exaltation, triplicity, bound, or their detriment/fall)": "Evaluar la dignidad del regente del signo del Lote de la Fortuna (domicilio, exaltación, triplicidad, límites, o su detrimento/caída)",
    "Generate Fortune houses by making the sign/house containing the Lot of Fortune the first house and count the rest accordingly for specific inquiries": "Generar las casas de Fortuna haciendo de la casa o signo que contiene el Lote de la Fortuna la primera casa y contando las demás en consecuencia para consultas específicas",
    "Apply zodiacal releasing from the Lot of Fortune to analyze periods of life, noting when the releasing arrives at angular, succedent, or cadent Fortune houses": "Aplicar liberación zodiacal desde el Lote de la Fortuna para analizar periodos de vida, observando cuándo la liberación llega a casas de Fortuna angulares, sucedentes o cadentes",
    "Determination of the condition of the Lot of Fortune regarding material prosperity, bodily well-being, and periods of activity via zodiacal releasing.": "Determinación de la condición del Lote de la Fortuna respecto de la prosperidad material, el bienestar corporal y los periodos de actividad mediante liberación zodiacal.",
    "Identify the sect light: Sun by day, Moon by night": "Identificar la luz de la secta: Sol de día, Luna de noche",
    "Check if the sect light is located in a valid house (per author: angular/succedent, releasing house, or specific list)": "Verificar si la luz de la secta se encuentra en una casa válida (según el autor: angular, sucedente, casa de liberación o lista específica)",
    "That body is the Predominator": "Ese cuerpo es el predominador",
    "The other light is chosen as Predominator": "La otra luminaria se elige como predominador",
    "Identification of the Predominator: Sun, Moon, or Ascendant as qualified by house, sect, and direction.": "Identificación del predominador: Sol, Luna o Ascendente según casa, secta y dirección.",
    "If the sect light is angular or succedent and in the east, then Sect light is Predominator": "Si la luz de la secta es angular o sucedente y está en el este, la luz de la secta es el predominador",
    "If sect light is cadent, then Disqualify sect light; examine contrary sect light": "Si la luz de la secta está cadente, descartar la luz de la secta y examinar la luminaria contraria a la secta",
    "If the light of the sect is cadent, then predomination may go to the other light if it satisfies the criteria": "Si la luz de la secta está cadente, la predominancia puede pasar a la otra luminaria si cumple los criterios",
    "If the sect light is disqualified, then light contrary to the sect is examined": "Si la luz de la secta queda descalificada, se examina la luminaria contraria a la secta",
    "the sect light is located in an authoritative/releasing house": "la luz de la secta se encuentra en una casa autoritativa o de liberación",
    "the sect light is not eligible, but the other light is in a valid house": "la luz de la secta no es elegible, pero la otra luminaria está en una casa válida",
    "Count forward (in zodiacal order) from the reference house to reach the derived house": "Contar hacia adelante (en orden zodiacal) desde la casa de referencia hasta llegar a la casa derivada",
    "Interpret the condition, planets, and aspects in the derived house for the question at hand": "Interpretar la condición, los planetas y los aspectos en la casa derivada para la cuestión planteada",
    "Identification of the derived house and its condition pertaining to the person or topic in question.": "Identificación de la casa derivada y de su condición en relación con la persona o asunto consultado.",
    "Check if the lord is in a house configured by whole-sign aspect to the Ascendant (houses 3, 4, 5, 7, 9, 10, 11) or in aversion (houses 2, 6, 8, 12)": "Verificar si el regente está en una casa configurada por aspecto de signo entero al Ascendente (casas 3, 4, 5, 7, 9, 10, 11) o en aversión (casas 2, 6, 8, 12)",
    "lord is in house in aversion": "el regente está en una casa en aversión",
    "domicile lord of Ascendant is in the first house and in good condition": "el regente domiciliario del Ascendente está en la primera casa y en buena condición",
    "Steering is difficult; path moves through challenging topics.": "La conducción se dificulta; el camino transcurre por temas desafiantes.",
    "Steering is difficult; path moves through challenging topics": "La conducción se dificulta; el camino transcurre por temas desafiantes.",
    "Native is strong, self-steering, with full power to direct life.": "El nativo es fuerte, se gobierna a sí mismo y posee plena capacidad para dirigir su vida.",
    "Native is strong, self-steering, with full power to direct life": "El nativo es fuerte, se gobierna a sí mismo y posee plena capacidad para dirigir su vida.",
    "The identification of the Predominator (Apheta/Hyleg) for purposes of assigning the Oikodespotes and for further longevity calculation.": "La identificación del predominador (apheta/hyleg) para asignar el oikodespotes y continuar el cálculo de longevidad.",
    "equal house system": "sistema de casas iguales",
    "planet s own natural signification": "significación natural propia del planeta",
    "Identify the planet's own natural significations": "Identificar las significaciones naturales propias del planeta",
    "For equal house system: Mark the degree of the Ascendant as the start of the first house; from there, each successive house is marked every 30° at the same degree in the following sign": "Para el sistema de casas iguales: marcar el grado del Ascendente como inicio de la primera casa; desde allí, cada casa sucesiva se marca cada 30° en el mismo grado del signo siguiente",
}

_UX_LITERAL_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("Master of the Nativity", "oikodespotes"),
    ("Joint-Master", "co-maestro"),
    ("bound lord", "regente de límites"),
    ("domicili lord", "regente domiciliario"),
    ("domicile lord", "regente domiciliario"),
    ("lords", "regentes"),
    (" lord ", " regente "),
    ("lord of the nativity", "regente de la natividad"),
    ("Predominator", "predominador"),
    ("Porphyry", "Porfirio"),
    ("Valens", "Valente"),
    ("conceptual role attribution", "atribución conceptual de rol"),
    ("procedure", "procedimiento"),
    ("method", "método"),
    ("concept", "concepto"),
    ("Ascendant", "Ascendente"),
    ("Descendant", "Descendente"),
    ("Midheaven", "Medio Cielo"),
    ("nativity", "natividad"),
)

_UX_REGEX_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bSun is predominador\b", re.IGNORECASE), "el Sol es el predominador"),
    (re.compile(r"\bMoon is predominador\b", re.IGNORECASE), "la Luna es el predominador"),
    (re.compile(r"\bLot of Fortune is predominador\b", re.IGNORECASE), "el Lote de la Fortuna es el predominador"),
    (re.compile(r"\bPrenatal Lunation is predominador\b", re.IGNORECASE), "la lunación prenatal es el predominador"),
    (
        re.compile(
            r"\bDefault to Ascendente or occasionally Medio Cielo or a derivative light or authoritative planet\b",
            re.IGNORECASE,
        ),
        "pasar al Ascendente o, ocasionalmente, al Medio Cielo o a una luminaria derivada o planeta con autoridad",
    ),
    (
        re.compile(r"\bthe Sun or Moon is not suitable to be the predominat(?:or|ador)\b", re.IGNORECASE),
        "el Sol o la Luna no son aptos para ser el predominador",
    ),
    (
        re.compile(
            r"\bthe regente de límites of the predominador is not witnessed by the predominador or is located in the Descendente\b",
            re.IGNORECASE,
        ),
        "el regente de límites del predominador no es testificado por el predominador o está ubicado en el Descendente",
    ),
    (
        re.compile(r"\bthe regente domiciliario of the predominador is used\b", re.IGNORECASE),
        "se usa el regente domiciliario del predominador",
    ),
    (
        re.compile(r"\bthe regente de límites of the predominador is used\b", re.IGNORECASE),
        "se usa el regente de límites del predominador",
    ),
    (
        re.compile(r"\bSun in first, tenth, or eleventh in day chart\b", re.IGNORECASE),
        "Sol en la primera, décima o undécima casa en carta diurna",
    ),
    (
        re.compile(r"\bMoon in second, first, eleventh, or tenth\b", re.IGNORECASE),
        "Luna en la segunda, primera, undécima o décima casa",
    ),
    (
        re.compile(r"\bBoth lights in cadent houses\b", re.IGNORECASE),
        "Ambas luminarias en casas cadentes",
    ),
    (
        re.compile(r"\bNo light, Lot, or Lunation qualifies\b", re.IGNORECASE),
        "Ninguna luminaria, lote o lunación califica",
    ),
    (
        re.compile(r"\bthe Moon is declining in the west \(ninth house\) and the Sun is in the second house\b", re.IGNORECASE),
        "la Luna declina en el oeste (novena casa) y el Sol está en la segunda casa",
    ),
    (
        re.compile(r"\bboth the Sun and Moon are under the horizon and both are in angular or succedent houses\b", re.IGNORECASE),
        "el Sol y la Luna están bajo el horizonte y ambos en casas angulares o sucedentes",
    ),
    (
        re.compile(r"both the Sun and Moon are cadent \(third and/or sixth houses\)", re.IGNORECASE),
        "el Sol y la Luna están cadentes (tercera y/o sexta casas)",
    ),
    (
        re.compile(r"\bthe preferred light is badly placed\b", re.IGNORECASE),
        "la luminaria preferida está mal ubicada",
    ),
    (
        re.compile(r"\brary sect light can predominate\b", re.IGNORECASE),
        "la luminaria contraria a la secta puede predominar",
    ),
    (
        re.compile(r"\bboth lights are too weak\b", re.IGNORECASE),
        "ambas luminarias son demasiado débiles",
    ),
    (
        re.compile(r"\bboth Sun and Moon are in the ninth or twelfth\b", re.IGNORECASE),
        "el Sol y la Luna están en la novena o la duodécima",
    ),
    (
        re.compile(r"\bneither light qualifies\b", re.IGNORECASE),
        "ninguna luminaria califica",
    ),
    (
        re.compile(r"\br both are cadent, predomination defaults to Ascendente\b", re.IGNORECASE),
        "si ambas están cadentes, la predominancia pasa al Ascendente",
    ),
    (
        re.compile(r"\bSun is in houses 1, 10, or 11, and is witnessed by its regente de límites within its own bounds\b", re.IGNORECASE),
        "el Sol está en las casas 1, 10 u 11 y es testificado por su regente de límites dentro de sus propios límites",
    ),
    (re.compile(r"\bSun is the predominador\b", re.IGNORECASE), "el Sol es el predominador"),
    (re.compile(r"\bIf so,\s*", re.IGNORECASE), "si es así, "),
    (
        re.compile(r"\bSun is in houses 1, 10, or 11, but not witnessed by its regente de límites within its own bounds, check for witnessing by triplicity, domicile, or exaltation lords by whole sign no aspect\b", re.IGNORECASE),
        "el Sol está en las casas 1, 10 u 11, pero no es testificado por su regente de límites dentro de sus propios límites; verificar testimonio por regentes de triplicidad, domicilio o exaltación por signo entero",
    ),
    (
        re.compile(r"\bSun is in houses 1, 10, or 11, but not witnessed by its regente de límites within its own bounds, check for witnessing by triplicity, domicile, or exaltation regentes by whole sign no aspect\b", re.IGNORECASE),
        "el Sol está en las casas 1, 10 u 11, pero no es testificado por su regente de límites dentro de sus propios límites; verificar testimonio por regentes de triplicidad, domicilio o exaltación por signo entero",
    ),
    (re.compile(r"If so, Sun is the predominador", re.IGNORECASE), "si es así, el Sol es el predominador"),
    (
        re.compile(r"\bMoon is in houses 1, 10, or 11 and is witnessed by its regente de límites within its own bounds\b", re.IGNORECASE),
        "la Luna está en las casas 1, 10 u 11 y es testificada por su regente de límites dentro de sus propios límites",
    ),
    (re.compile(r"\bMoon is the predominador\b", re.IGNORECASE), "la Luna es el predominador"),
    (
        re.compile(r"\bneither Sun nor Moon qualify, repeat full process with Lot of Fortune\b", re.IGNORECASE),
        "ni el Sol ni la Luna califican; repetir el proceso completo con el Lote de la Fortuna",
    ),
    (
        re.compile(r"\bno candidate qualifies, default to Ascendente\b", re.IGNORECASE),
        "ningún candidato califica; pasar al Ascendente",
    ),
    (
        re.compile(r"\bnone of these qualify\b", re.IGNORECASE),
        "ninguno de estos califica",
    ),
    (
        re.compile(r"\bthe oikodespotes is in aversion to the predominador \(Valente & Paulus methods\)\b", re.IGNORECASE),
        "el oikodespotes está en aversión al predominador (métodos de Valente y Paulus)",
    ),
    (
        re.compile(r"the oikodespotes is in aversion to the predominador \(Valente & Paulus métodos\)", re.IGNORECASE),
        "el oikodespotes está en aversión al predominador (métodos de Valente y Paulus)",
    ),
    (
        re.compile(r"\bthe sect light is angular or succedent and in the east\b", re.IGNORECASE),
        "la luz de la secta es angular o sucedente y está en el este",
    ),
    (
        re.compile(r"\bsect light is cadent\b", re.IGNORECASE),
        "la luz de la secta está cadente",
    ),
    (
        re.compile(r"\bboth lights are cadent\b", re.IGNORECASE),
        "ambas luminarias están cadentes",
    ),
    (
        re.compile(r"\bboth the Sun and Moon are cadent \(third and/or sixth houses\)\b", re.IGNORECASE),
        "el Sol y la Luna están cadentes (tercera y/o sexta casas)",
    ),
    (
        re.compile(r"\bpredomination goes to Ascendente\b", re.IGNORECASE),
        "la predominancia pasa al Ascendente",
    ),
    (
        re.compile(r"\bthe light of the sect is cadent\b", re.IGNORECASE),
        "la luz de la secta está cadente",
    ),
    (
        re.compile(r"\bthe sect light is disqualified\b", re.IGNORECASE),
        "la luz de la secta queda descalificada",
    ),
    (
        re.compile(r"\bboth lights are disqualified due to cadency\b", re.IGNORECASE),
        "ambas luminarias quedan descalificadas por cadencia",
    ),
    (
        re.compile(r"\bing, and being westerly, predomination usually goes to the Ascendente\b", re.IGNORECASE),
        "al estar occidentales, la predominancia suele pasar al Ascendente",
    ),
    (re.compile(r"\bit becomes the oikodespotes\b", re.IGNORECASE), "se convierte en el oikodespotes"),
    (re.compile(r"\bit qualifies as oikodespotes\b", re.IGNORECASE), "califica como oikodespotes"),
    (
        re.compile(r"\bla natividad puede carecer de oikodespotes \(.+\)\b", re.IGNORECASE),
        "la natividad puede carecer de oikodespotes",
    ),
    (
        re.compile(r"la natividad puede carecer de oikodespotes \([^)]+\)", re.IGNORECASE),
        "la natividad puede carecer de oikodespotes",
    ),
    (
        re.compile(r"\bthe planet is contrary to sect, detrimented, afflicted by malefics, or cadent\b", re.IGNORECASE),
        "el planeta es contrario a la secta, está en detrimento, afligido por maléficos o cadente",
    ),
    (
        re.compile(r"\bxiste oikodespotes for the natividad according to Valente\b", re.IGNORECASE),
        "no existe oikodespotes para la natividad según Valente",
    ),
    (re.compile(r"\bxiste Oikodespotes\b", re.IGNORECASE), "no existe oikodespotes"),
    (re.compile(r"\bOikodespotes\b"), "oikodespotes"),
)

_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_AUTO_FRAME_MIN_SIGNAL = 1

_AUTO_FRAME_LABELS_ES: dict[str, str] = {
    "equal house system": "Sistema de casas iguales",
    "planet s own natural signification": "Significación natural propia del planeta",
}

_AUTO_FRAME_GOAL_TEMPLATES_ES: dict[str, str] = {
    "selection": "Identificar y estructurar el procedimiento de {concept}.",
    "evaluation": "Evaluar la condición y los resultados asociados con {concept}.",
    "timing": "Aplicar el procedimiento temporal asociado con {concept}.",
    "analysis": "Analizar el procedimiento asociado con {concept}.",
}


def _dedupe_list(items: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _translate_text(value: str) -> str:
    normalized = _normalize_text(value)
    translated = _TEXT_ES.get(normalized, normalized)
    for source, target in _UX_LITERAL_REPLACEMENTS:
        translated = translated.replace(source, target)
    for pattern, replacement in _UX_REGEX_REPLACEMENTS:
        translated = pattern.sub(replacement, translated)
    return _normalize_text(translated)


def _normalize_text(value: str) -> str:
    return _SPACE_RE.sub(" ", str(value).strip())


def _surface(value: str) -> str:
    normalized = _normalize_text(value).lower().replace("-", " ")
    normalized = _PUNCT_RE.sub(" ", normalized)
    return _SPACE_RE.sub(" ", normalized).strip()


def _text_has_any_signal(text: str, signals: tuple[str, ...]) -> bool:
    blob = _surface(text)
    return any(_surface(signal) in blob for signal in signals)


def _text_passes_filters(text: str, spec: dict[str, Any]) -> bool:
    include = tuple(spec.get("include_signals", ()))
    exclude = tuple(spec.get("exclude_signals", ()))
    if include and not _text_has_any_signal(text, include):
        return False
    if exclude and _text_has_any_signal(text, exclude):
        return False
    return True


def _normalize_condition(value: str) -> str:
    text = _normalize_text(value)
    text = re.sub(r"^(?:if|si)\s+", "", text, flags=re.IGNORECASE)
    return text.strip(" .;:")


def _normalize_outcome(value: str) -> str:
    return _normalize_text(value).strip(" .;:")


def _sentence_case(value: str) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    return text[0].upper() + text[1:]


def _rule_quality(condition: str, outcome: str) -> bool:
    c = _surface(condition)
    o = _surface(outcome)
    if not c or not o:
        return False
    if "e g" in c:
        return False
    if o.startswith(("first ", "second ", "third ", "fourth ", "fifth ", "sixth ", "seventh ", "eighth ", "ninth ", "tenth ", "eleventh ", "twelfth ")):
        return False
    if o.startswith("r if ") or o.startswith("re is no "):
        return False
    return True


def _normalize_rule(rule: dict[str, Any]) -> dict[str, Any] | None:
    condition = _normalize_condition(str(rule.get("condition", "")))
    outcome = _normalize_outcome(str(rule.get("outcome", "")))
    if not _rule_quality(condition, outcome):
        return None
    return {
        "condition": condition,
        "outcome": outcome,
        "related_steps": [str(v).strip() for v in rule.get("related_steps", []) if str(v).strip()],
    }


def _rule_text(rule: dict[str, Any]) -> str:
    return f"{rule.get('condition', '')} {rule.get('outcome', '')}"


def _rule_key(rule: dict[str, Any]) -> tuple[str, str]:
    condition = _surface(str(rule.get("condition", "")))
    outcome = _surface(str(rule.get("outcome", "")))
    outcome = outcome.replace("will be the predominator", "is the predominator")
    outcome = outcome.replace("the predomination goes to the ascendant", "predomination goes to the ascendant")
    outcome = outcome.replace("predomination goes to the ascendant", "the ascendant has the predomination")
    outcome = outcome.replace("the ascendant will have the predomination", "the ascendant has the predomination")
    outcome = outcome.replace("moon will be the predominator", "moon is the predominator")
    return condition, outcome


def _rule_priority(rule: dict[str, Any]) -> tuple[int, str, str]:
    condition, outcome = _rule_key(rule)
    if "light of the sect is cadent" in condition and "other light" in outcome:
        return (1, condition, outcome)
    if "moon" in condition and "ascending in the east" in condition and "predominator" in outcome:
        return (2, condition, outcome)
    if ("both lights" in condition or ("sun" in condition and "moon" in condition)) and (
        "cadent" in condition or "declining" in condition
    ) and "ascendant" in outcome:
        return (3, condition, outcome)
    if "bound lord" in condition or "domicile lord" in condition:
        return (4, condition, outcome)
    return (50, condition, outcome)


def _step_id(order: int, text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _surface(text)).strip("-")[:48] or "step"
    return f"step-{order:03d}-{slug}"


def _step_from_rule(rule: dict[str, Any], order: int) -> dict[str, Any]:
    text = _sentence_case(f"If {rule['condition']}, then {rule['outcome']}")
    return {"id": _step_id(order, text), "order": order, "text": text}


def _normalize_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in sorted(steps, key=lambda step: (int(step.get("order", 0)), str(step.get("id", "")))):
        text = _normalize_text(str(item.get("text", ""))).strip(" .;:")
        if not text:
            continue
        key = _surface(text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"id": str(item.get("id") or _step_id(len(deduped) + 1, text)), "order": len(deduped) + 1, "text": text})
    return deduped


def _derive_shared_steps(frame: dict[str, Any]) -> list[dict[str, Any]]:
    explicit = _normalize_steps(list(frame.get("shared_steps", [])))
    if len(explicit) >= 2:
        return explicit
    rules = [rule for raw in frame.get("decision_rules", []) if (rule := _normalize_rule(raw)) is not None]
    ranked = sorted(rules, key=_rule_priority)
    derived: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for raw_rule in ranked:
        key = _rule_key(raw_rule)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        derived.append(_step_from_rule(raw_rule, len(derived) + 1))
        if len(derived) >= 3:
            break
    if len(derived) >= 2:
        return derived
    return explicit


def _normalize_author_variants(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        normalized = {
            "author": _normalize_text(str(item.get("author", ""))),
            "kind": _normalize_text(str(item.get("kind", ""))),
            "text": _normalize_text(str(item.get("text", ""))),
            "related_steps": [str(v).strip() for v in item.get("related_steps", []) if str(v).strip()],
            "operation": _normalize_text(str(item.get("operation", ""))) or "annotate",
        }
        key = (_surface(normalized["author"]), _surface(normalized["kind"]), _surface(normalized["text"]))
        if not key[2] or key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _localize_author_variants(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    localized: list[dict[str, Any]] = []
    for item in items:
        localized.append(
            {
                **item,
                "author": _translate_text(str(item.get("author", ""))),
                "kind": _translate_text(str(item.get("kind", ""))),
                "text": _translate_text(str(item.get("text", ""))),
            }
        )
    return localized


def _selection_rule_kind(rule: dict[str, Any]) -> str:
    condition, outcome = _rule_key(rule)
    blob = f"{condition} {outcome}"
    if any(token in blob for token in ("other light", "contrary light", "ascendant")):
        return "fallback"
    if any(token in outcome for token in ("select ", "is the predominator", "qualifies as", "becomes the master", "is selected as master")):
        return "candidate"
    return "candidate"


def _split_selection_rules(rules: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_priority_rules: list[dict[str, Any]] = []
    fallback_rules: list[dict[str, Any]] = []
    for rule in rules:
        if _selection_rule_kind(rule) == "fallback":
            fallback_rules.append(rule)
        else:
            candidate_priority_rules.append(rule)
    return candidate_priority_rules, fallback_rules


def _derived_rules_from_author_methods(items: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    if spec.get("frame_type") != "selection":
        return []
    derived: list[dict[str, Any]] = []
    for item in items:
        author = _normalize_text(str(item.get("author", ""))) or "This method"
        text = _surface(str(item.get("text", "")))
        rule: dict[str, Any] | None = None
        if "domicile lord of the predominator" in text:
            rule = {
                "condition": f"{author}'s method is followed",
                "outcome": "select the domicile lord of the Predominator as Oikodespotes",
                "related_steps": [],
            }
        elif "bound lord of the predominator" in text:
            rule = {
                "condition": f"{author}'s method is followed",
                "outcome": "select the bound lord of the Predominator as Oikodespotes",
                "related_steps": [],
            }
        elif "bound lord of the ascendant" in text:
            rule = {
                "condition": f"{author}'s method is followed",
                "outcome": "select the bound lord of the Ascendant as Master of the Nativity",
                "related_steps": [],
            }
        elif "sign following the natal moon" in text:
            rule = {
                "condition": f"{author}'s method is followed",
                "outcome": "select the domicile lord of the sign following the natal Moon as Oikodespotes",
                "related_steps": [],
            }
        if rule is not None and _text_passes_filters(_rule_text(rule), spec):
            derived.append(rule)
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for rule in derived:
        key = _rule_key(rule)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rule)
    return deduped


def _classify_author_variant(item: dict[str, Any], spec: dict[str, Any]) -> str:
    text = f"{item.get('kind', '')} {item.get('text', '')}"
    if not _text_passes_filters(text, spec):
        return "skip"
    blob = _surface(text)
    if spec.get("frame_type") == "selection" and any(
        token in blob
        for token in ("house system", "whole sign", "whole-sign", "porphyry house system", "terminological", "unclear if used")
    ):
        return "methodological_note"
    if any(token in blob for token in ("method", "procedure", "assignment", "assigns", "looked for", "determining", "determine", "select")):
        return "author_method"
    return "override"


def _derived_evaluation_rules_from_technical_rules(rules: list[str], spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    derived_rules: list[dict[str, Any]] = []
    derived_preconditions: list[dict[str, Any]] = []
    for raw in rules:
        text = _normalize_text(raw)
        if not text or not _text_passes_filters(text, spec):
            continue
        lowered = _surface(text)
        if lowered.startswith("when "):
            parts = text[5:].split(",", 1)
            if len(parts) == 2:
                condition, outcome = parts
                rule = _normalize_rule({"condition": condition, "outcome": outcome, "related_steps": []})
                if rule is not None:
                    derived_rules.append(rule)
                    continue
        if lowered.startswith("if "):
            parts = text[3:].split(",", 1)
            if len(parts) == 2:
                condition, outcome = parts
                rule = _normalize_rule({"condition": condition, "outcome": outcome, "related_steps": []})
                if rule is not None:
                    derived_rules.append(rule)
                    continue
        if lowered.startswith("in delineation consider if "):
            body = text[len("In delineation, consider if "):]
            for piece in body.split(","):
                piece = _normalize_text(piece)
                if piece:
                    derived_preconditions.append({"text": piece, "scope": "evaluation of the Oikodespotes", "related_steps": []})
            continue
        if "belongs to the sect of the chart" in lowered or "angular or succedent houses" in lowered or "own domiciles or exaltation" in lowered:
            derived_preconditions.append({"text": text, "scope": "evaluation of the Oikodespotes", "related_steps": []})
    deduped_rules: list[dict[str, Any]] = []
    seen_rule_keys: set[tuple[str, str]] = set()
    for rule in derived_rules:
        key = _rule_key(rule)
        if key in seen_rule_keys:
            continue
        seen_rule_keys.add(key)
        deduped_rules.append(rule)
    deduped_pre: list[dict[str, Any]] = []
    seen_pre: set[tuple[str, str]] = set()
    for item in derived_preconditions:
        key = (_surface(item["text"]), _surface(item["scope"]))
        if key in seen_pre:
            continue
        seen_pre.add(key)
        deduped_pre.append(item)
    return deduped_rules, deduped_pre


def _empty_evidence() -> dict[str, list[dict[str, Any]]]:
    return {
        "shared_steps": [],
        "decision_rules": [],
        "preconditions": [],
        "exceptions": [],
        "author_variant_overrides": [],
        "author_method_variants": [],
        "procedure_outputs": [],
    }


def _append_step(steps: list[dict[str, Any]], text: str) -> None:
    normalized = _normalize_text(text).strip(" .;:")
    if not normalized:
        return
    key = _surface(normalized)
    if any(_surface(str(item.get("text", ""))) == key for item in steps):
        return
    order = len(steps) + 1
    steps.append({"id": _step_id(order, normalized), "order": order, "text": normalized})


def _derive_timing_steps_from_texts(frame: dict[str, Any]) -> list[dict[str, Any]]:
    steps = _normalize_steps(list(frame.get("shared_steps", [])))
    blob = _surface(" ".join(frame.get("_definitions", []) + frame.get("_technical_rules", [])))
    if not blob:
        return steps

    if len(steps) < 1 and ("profection" in blob or "annual lord" in blob or "time lord" in blob):
        _append_step(steps, "Select the type of profection (annual, monthly, daily) according to the timing interval required")
    if "activated" in blob and "zodiacal order" in blob:
        _append_step(steps, "Activate the next sign in zodiacal order at each interval")
    if "house occupied by the profected sign" in blob or "matters of the house occupied by the profected sign" in blob:
        _append_step(steps, "Emphasize the matters of the house occupied by the profected sign for that period")
    if "planet that rules the profected sign" in blob or "time lord" in blob:
        _append_step(steps, "Identify the planet that rules the profected sign (the time lord)")
    if "bring about its significations" in blob or "governs the life for the duration" in blob:
        _append_step(steps, "Interpret the effect of the time lord during its period of influence based on its significations in the natal chart")
    return _normalize_steps(steps)


def _derive_selection_steps(frame: dict[str, Any]) -> list[dict[str, Any]]:
    explicit = _normalize_steps(list(frame.get("shared_steps", [])))
    if len(explicit) >= 3:
        return explicit

    derived: list[dict[str, Any]] = []
    ordered_rules = sorted(
        list(frame.get("candidate_priority_rules", [])) + list(frame.get("fallback_rules", [])),
        key=_rule_priority,
    )
    for rule in ordered_rules:
        normalized = _normalize_rule(rule)
        if normalized is None:
            continue
        key = _rule_key(normalized)
        if any(_surface(step.get("text", "")) == _surface(_step_from_rule(normalized, 1)["text"]) for step in derived):
            continue
        derived.append(_step_from_rule(normalized, len(derived) + 1))
        if len(derived) >= 4:
            break
    if len(derived) >= 2:
        return _normalize_steps(derived)
    return explicit


def _merge_evidence(target: dict[str, list[dict[str, Any]]], source: dict[str, Any]) -> None:
    mapping = {
        "procedure_steps": "shared_steps",
        "decision_rules": "decision_rules",
        "preconditions": "preconditions",
        "exceptions": "exceptions",
        "author_variants": "author_variant_overrides",
        "procedure_outputs": "procedure_outputs",
    }
    for source_key, target_key in mapping.items():
        values = source.get(source_key, [])
        if not isinstance(values, list):
            continue
        for item in values:
            if item not in target[target_key]:
                target[target_key].append(item)


def _has_procedural_content(record: dict[str, Any]) -> bool:
    return any(
        record.get(field_name)
        for field_name in (
            "shared_procedure",
            "decision_rules",
            "preconditions",
            "exceptions",
            "author_variant_overrides",
            "procedure_outputs",
        )
    )


def _collect_member_records(
    concepts: dict[str, dict[str, Any]],
    spec: dict[str, Any],
) -> tuple[list[str], list[str], list[tuple[str, dict[str, Any]]]]:
    anchors = [concept for concept in spec["anchor_concepts"] if concept in concepts]
    supports = [concept for concept in spec["supporting_concepts"] if concept in concepts]
    members = anchors + [concept for concept in supports if concept not in anchors]
    records = [
        (concept, concepts[concept])
        for concept in members
        if _has_procedural_content(concepts[concept])
    ]
    return anchors, supports, records


def _filter_steps(steps: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        step for step in steps
        if _text_passes_filters(str(step.get("text", "")), spec)
    ]


def _filter_rules(rules: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen_rule_keys: set[tuple[str, str]] = set()
    for raw_rule in rules:
        rule = _normalize_rule(raw_rule)
        if rule is None:
            continue
        if not _text_passes_filters(_rule_text(rule), spec):
            continue
        key = _rule_key(rule)
        if key in seen_rule_keys:
            continue
        seen_rule_keys.add(key)
        filtered.append(rule)
    return filtered


def _filter_conditions(items: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        text = _normalize_text(str(item.get("text", "")))
        scope = _normalize_text(str(item.get("scope", "")))
        if not text or not _text_passes_filters(f"{scope} {text}", spec):
            continue
        key = (_surface(text), _surface(scope))
        if key in seen:
            continue
        seen.add(key)
        filtered.append(
            {
                "text": text,
                "scope": scope,
                "related_steps": [str(v).strip() for v in item.get("related_steps", []) if str(v).strip()],
            }
        )
    return filtered


def _filter_outputs(items: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        text = _normalize_text(str(item.get("text", "")))
        if not text or not _text_passes_filters(text, spec):
            continue
        key = _surface(text)
        if key in seen:
            continue
        seen.add(key)
        filtered.append({"text": text})
    return filtered


def _title_case_words(value: str) -> str:
    words = [part for part in _normalize_text(value).split(" ") if part]
    if not words:
        return ""
    return " ".join(word[:1].upper() + word[1:] for word in words)


def _auto_frame_id(concept_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", _surface(concept_name)).strip("_") or "procedure"
    return f"auto_{slug}"


def _infer_auto_frame_type(concept_name: str, record: dict[str, Any]) -> str:
    blob = _surface(
        " ".join(
            [concept_name]
            + [str(item.get("text", "")) for item in record.get("shared_procedure", [])]
            + [f"{item.get('condition', '')} {item.get('outcome', '')}" for item in record.get("decision_rules", [])]
            + list(record.get("definitions", []))
            + list(record.get("technical_rules", []))
            + [str(item.get("text", "")) for item in record.get("procedure_outputs", [])]
        )
    )
    if any(token in blob for token in ("profection", "time lord", "chronokrator", "timing", "releasing")):
        return "timing"
    if record.get("decision_rules"):
        if any(token in blob for token in ("good condition", "bad condition", "self steering", "strong", "weak", "difficult")):
            return "evaluation"
        return "selection"
    if any(token in blob for token in ("evaluate", "condition", "good condition", "bad condition", "self steering")):
        return "evaluation"
    if any(token in blob for token in ("select", "determine", "choose")):
        return "selection"
    return "analysis"


def _auto_frame_goal(frame_type: str, concept_name: str) -> str:
    concept_es = _translate_text(concept_name)
    template = _AUTO_FRAME_GOAL_TEMPLATES_ES.get(frame_type, _AUTO_FRAME_GOAL_TEMPLATES_ES["analysis"])
    return template.format(concept=concept_es)


def _finalize_frame(frame: dict[str, Any]) -> dict[str, Any]:
    frame["label"] = _FRAME_LABELS_ES.get(frame["id"], frame["label"])
    frame["goal"] = _FRAME_GOALS_ES.get(frame["id"], frame["goal"])
    localized_steps: list[dict[str, Any]] = []
    for step in frame["shared_steps"]:
        localized_step = dict(step)
        localized_step["text"] = _translate_text(str(step.get("text", "")))
        localized_steps.append(localized_step)
    frame["shared_steps"] = _normalize_steps(localized_steps)
    frame["decision_rules"] = [
        {
            **rule,
            "condition": _translate_text(str(rule.get("condition", ""))),
            "outcome": _translate_text(str(rule.get("outcome", ""))),
        }
        for rule in frame["decision_rules"]
    ]
    frame["candidate_priority_rules"] = [
        {
            **rule,
            "condition": _translate_text(str(rule.get("condition", ""))),
            "outcome": _translate_text(str(rule.get("outcome", ""))),
        }
        for rule in frame["candidate_priority_rules"]
    ]
    frame["fallback_rules"] = [
        {
            **rule,
            "condition": _translate_text(str(rule.get("condition", ""))),
            "outcome": _translate_text(str(rule.get("outcome", ""))),
        }
        for rule in frame["fallback_rules"]
    ]
    frame["procedure_outputs"] = [
        {"text": _translate_text(str(item.get("text", "")))}
        for item in frame["procedure_outputs"]
    ]
    frame["author_method_variants"] = _localize_author_variants(frame["author_method_variants"])
    frame["author_variant_overrides"] = _localize_author_variants(frame["author_variant_overrides"])
    frame["methodological_notes"] = _localize_author_variants(frame["methodological_notes"])
    frame.pop("_definitions", None)
    frame.pop("_technical_rules", None)
    return frame


def _build_auto_frames(
    concepts: dict[str, dict[str, Any]],
    existing_frames: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    covered_concepts: set[str] = set()
    for frame in existing_frames.values():
        covered_concepts.update(frame.get("anchor_concepts", []))
        covered_concepts.update(frame.get("supporting_concepts", []))

    auto_frames: dict[str, dict[str, Any]] = {}
    passthrough_spec = {"include_signals": (), "exclude_signals": ()}
    for concept_name, record in concepts.items():
        if concept_name in covered_concepts or not _has_procedural_content(record):
            continue
        signal = (
            len(record.get("shared_procedure", []))
            + len(record.get("decision_rules", []))
            + len(record.get("procedure_outputs", []))
        )
        if signal < _AUTO_FRAME_MIN_SIGNAL:
            continue
        frame_type = _infer_auto_frame_type(concept_name, record)
        label = _AUTO_FRAME_LABELS_ES.get(concept_name, _title_case_words(_translate_text(concept_name)))
        frame = {
            "id": _auto_frame_id(concept_name),
            "frame_type": frame_type,
            "label": label,
            "goal": _auto_frame_goal(frame_type, concept_name),
            "anchor_concepts": [concept_name],
            "supporting_concepts": [],
            "shared_steps": _filter_steps(_normalize_steps(list(record.get("shared_procedure", []))), passthrough_spec),
            "decision_rules": _filter_rules(list(record.get("decision_rules", [])), passthrough_spec),
            "preconditions": _filter_conditions(list(record.get("preconditions", [])), passthrough_spec),
            "exceptions": _filter_conditions(list(record.get("exceptions", [])), passthrough_spec),
            "candidate_priority_rules": [],
            "fallback_rules": [],
            "author_method_variants": _normalize_author_variants(list(record.get("author_method_variants", []))),
            "author_variant_overrides": _normalize_author_variants(list(record.get("author_variant_overrides", []))),
            "methodological_notes": [],
            "procedure_outputs": _filter_outputs(list(record.get("procedure_outputs", [])), passthrough_spec),
            "related_concepts": _dedupe_list(
                list(record.get("related_concepts", []))
                + list(record.get("parent_concepts", []))
                + list(record.get("child_concepts", []))
            ),
            "evidence": _empty_evidence(),
            "source_chunks": _dedupe_list(list(record.get("source_chunks", []))),
            "_definitions": _dedupe_list(list(record.get("definitions", []))),
            "_technical_rules": _dedupe_list(list(record.get("technical_rules", []))),
        }
        if frame_type == "selection":
            frame["candidate_priority_rules"], frame["fallback_rules"] = _split_selection_rules(frame["decision_rules"])
            frame["shared_steps"] = _derive_selection_steps(frame)
        elif frame_type == "timing":
            frame["shared_steps"] = _derive_timing_steps_from_texts(frame)
        else:
            frame["shared_steps"] = _derive_shared_steps(frame)
        auto_frames[frame["id"]] = _finalize_frame(frame)
    return auto_frames


def build_procedure_frames(
    concepts: dict[str, dict[str, Any]],
    ontology: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    frames: dict[str, dict[str, Any]] = {}
    for spec in _FRAME_SPECS:
        anchors, supports, records = _collect_member_records(concepts, spec)
        if not records:
            continue

        frame = {
            "id": spec["id"],
            "frame_type": spec["frame_type"],
            "label": spec["label"],
            "goal": spec["goal"],
            "anchor_concepts": anchors,
            "supporting_concepts": [concept for concept in supports if concept not in anchors],
            "shared_steps": [],
            "decision_rules": [],
            "preconditions": [],
            "exceptions": [],
            "candidate_priority_rules": [],
            "fallback_rules": [],
            "author_method_variants": [],
            "author_variant_overrides": [],
            "methodological_notes": [],
            "procedure_outputs": [],
            "related_concepts": [],
            "evidence": _empty_evidence(),
            "source_chunks": [],
            "_definitions": [],
            "_technical_rules": [],
        }

        related = list(spec.get("related_concepts", ()))
        for concept_name, record in records:
            frame["shared_steps"] = _dedupe_list(frame["shared_steps"] + list(record.get("shared_procedure", [])))
            frame["decision_rules"] = _dedupe_list(frame["decision_rules"] + list(record.get("decision_rules", [])))
            frame["preconditions"] = _dedupe_list(frame["preconditions"] + list(record.get("preconditions", [])))
            frame["exceptions"] = _dedupe_list(frame["exceptions"] + list(record.get("exceptions", [])))
            frame["procedure_outputs"] = _dedupe_list(frame["procedure_outputs"] + list(record.get("procedure_outputs", [])))
            frame["source_chunks"] = _dedupe_list(frame["source_chunks"] + list(record.get("source_chunks", [])))
            frame["_definitions"] = _dedupe_list(frame["_definitions"] + list(record.get("definitions", [])))
            frame["_technical_rules"] = _dedupe_list(frame["_technical_rules"] + list(record.get("technical_rules", [])))
            related = _dedupe_list(
                related
                + list(record.get("related_concepts", []))
                + list(record.get("parent_concepts", []))
                + list(record.get("child_concepts", []))
            )
            for variant in record.get("author_variant_overrides", []):
                classification = _classify_author_variant(variant, spec)
                if classification == "author_method":
                    frame["author_method_variants"].append(variant)
                elif classification == "methodological_note":
                    frame["methodological_notes"].append(variant)
                elif classification == "override":
                    frame["author_variant_overrides"].append(variant)
            _merge_evidence(frame["evidence"], record.get("procedure_evidence", {}))

        frame["decision_rules"] = _filter_rules(frame["decision_rules"], spec)
        frame["preconditions"] = _filter_conditions(frame["preconditions"], spec)
        frame["exceptions"] = _filter_conditions(frame["exceptions"], spec)
        frame["procedure_outputs"] = _filter_outputs(frame["procedure_outputs"], spec)
        frame["author_method_variants"] = _normalize_author_variants(frame["author_method_variants"])
        frame["author_variant_overrides"] = _normalize_author_variants(frame["author_variant_overrides"])
        frame["methodological_notes"] = _normalize_author_variants(frame["methodological_notes"])
        if spec.get("frame_type") == "evaluation":
            derived_rules, derived_preconditions = _derived_evaluation_rules_from_technical_rules(frame["_technical_rules"], spec)
            frame["decision_rules"] = _filter_rules(frame["decision_rules"] + derived_rules, spec)
            frame["preconditions"] = _filter_conditions(frame["preconditions"] + derived_preconditions, spec)
        if not frame["decision_rules"] and frame["author_method_variants"]:
            frame["decision_rules"] = _derived_rules_from_author_methods(frame["author_method_variants"], spec)
        if spec.get("frame_type") == "selection":
            frame["candidate_priority_rules"], frame["fallback_rules"] = _split_selection_rules(frame["decision_rules"])
        if spec.get("frame_type") == "timing":
            frame["shared_steps"] = _derive_timing_steps_from_texts(frame)
        if spec.get("frame_type") == "selection":
            frame["shared_steps"] = _filter_steps(_derive_selection_steps(frame), spec)
        else:
            frame["shared_steps"] = _filter_steps(_derive_shared_steps(frame), spec)

        if not any(
            frame.get(field_name)
            for field_name in (
                "shared_steps",
                "decision_rules",
                "preconditions",
                "exceptions",
                "candidate_priority_rules",
                "fallback_rules",
                "author_method_variants",
                "author_variant_overrides",
                "methodological_notes",
                "procedure_outputs",
            )
        ):
            continue

        frame["related_concepts"] = [
            concept
            for concept in _dedupe_list(related)
            if concept not in frame["anchor_concepts"] and concept not in frame["supporting_concepts"]
        ]
        frames[frame["id"]] = _finalize_frame(frame)

    frames.update(_build_auto_frames(concepts, frames))
    return frames
