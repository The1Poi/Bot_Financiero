"""
Módulo 3: Validación de Entradas y Conversión Monetaria (RF03, RF04, RF06, RF07, Tabla XII).
Realiza la validación sintáctica y semántica del monto y del concepto, convierte montos
decimales a centavos enteros (INTEGER) sin usar punto flotante IEEE 754 (float),
y clasifica las entradas en el alfabeto formal Σ = {c, mv, mi, tv, ti, e}.
"""
import re
from decimal import Decimal, InvalidOperation

# Expresión regular sintáctica para montos positivos con hasta 2 decimales (ej. 15500 o 15500.50)
REGEX_MONTO = re.compile(r"^\d+(\.\d{1,2})?$")

# Límite máximo de caracteres permitido para el concepto de un gasto
MAX_CONCEPT_LENGTH = 150

# Expresión regular para detectar preguntas o consultas fuera de secuencia (ej. Fig. 7: "¿Cuáles son mis reportes del mes?")
REGEX_CONSULTA_FUERA_SECUENCIA = re.compile(
    r"(^/.*)|([¿?])|\b(reportes?|estad[ií]sticas?|ayuda|informaci[oó]n|saldo|consultar|cu[aá]les|cu[aá]nto)\b",
    re.IGNORECASE,
)


def validar_y_convertir_monto(texto: str) -> tuple[bool, int | None]:
    """
    Valida sintáctica y semánticamente un monto (RF03) y lo convierte a centavos enteros (Tabla XII).

    Retorna:
        (es_valido, monto_en_centavos)
        Ejemplo: "15500.50" -> (True, 1550050)
    """
    if not isinstance(texto, str):
        return False, None

    limpio = texto.strip()
    if not limpio or not REGEX_MONTO.match(limpio):
        return False, None

    try:
        valor_decimal = Decimal(limpio)
    except InvalidOperation:
        return False, None

    # Validación semántica: el monto debe ser estrictamente positivo (> 0)
    if valor_decimal <= Decimal("0"):
        return False, None

    # Conversión exacta a unidades monetarias menores (centavos) como INTEGER (Tabla XII)
    centavos = int((valor_decimal * Decimal("100")).to_integral_value())
    return True, centavos


def formatear_centavos_a_moneda(centavos: int) -> str:
    """
    Convierte un entero en centavos al formato visual de los mockups (ej. 1550050 -> '$15,500.50').
    """
    valor = Decimal(centavos) / Decimal("100")
    return f"${valor:,.2f}"


def validar_concepto(texto: str) -> tuple[bool, str]:
    """
    Valida sintáctica y semánticamente el concepto del gasto (RF06, RF07, Fig. 6).
    Rechaza textos vacíos, solo espacios o cadenas de solo símbolos/guiones (como '- - -').
    """
    if not isinstance(texto, str):
        return False, ""

    limpio = " ".join(texto.strip().split())
    if not limpio:
        return False, ""

    # Debe contener al menos un carácter alfanumérico real (rechaza "- - -", "...", etc. como en la Fig. 6)
    if not any(ch.isalnum() for ch in limpio):
        return False, ""

    # Límite estricto de 150 caracteres para evitar saturación en concepto
    if len(limpio) > MAX_CONCEPT_LENGTH:
        return False, ""

    return True, limpio


def clasificar_entrada(estado_actual: str, texto: str) -> str:
    """
    Clasifica el texto del usuario en uno de los símbolos del alfabeto formal del AFD:
    Σ = {'c', 'mv', 'mi', 'tv', 'ti', 'e'} según la Tabla XI del documento IEEE.

    Donde:
      - 'c'  : Comando /gasto
      - 'mv' : Monto válido
      - 'mi' : Monto inválido
      - 'tv' : Concepto válido
      - 'ti' : Concepto inválido
      - 'e'  : Mensaje fuera de secuencia
    """
    limpio = (texto or "").strip()
    comando_base = limpio.split()[0].lower().split("@")[0] if limpio else ""

    # 1. El comando /gasto siempre corresponde al símbolo 'c'
    if comando_base == "/gasto":
        return "c"

    # 2. Cualquier otro comando con '/' (ej. /informacion, /reporte, /start) durante el flujo es 'e' (fuera de secuencia)
    if limpio.startswith("/"):
        return "e"

    # 3. Evaluación contextual según la etapa del registro:
    if estado_actual == "S1":
        # En S1 (Esperando Monto):
        # Si es una pregunta/consulta ajena al monto (como "¿Cuáles son mis reportes del mes?" de la Fig. 7) -> 'e'
        if REGEX_CONSULTA_FUERA_SECUENCIA.search(limpio):
            return "e"
        es_monto, _ = validar_y_convertir_monto(limpio)
        return "mv" if es_monto else "mi"

    if estado_actual == "S2":
        # En S2 (Esperando Concepto):
        # Si es una pregunta/consulta de sistema con signos de interrogación -> 'e'
        if "?" in limpio or "¿" in limpio:
            return "e"
        # Si el usuario envía únicamente un número puro en lugar de un concepto descriptivo -> 'ti' o 'tv'
        es_concepto, _ = validar_concepto(limpio)
        return "tv" if es_concepto else "ti"

    # En S0 (Inactivo), cualquier entrada que no sea /gasto es fuera de secuencia ('e')
    return "e"
