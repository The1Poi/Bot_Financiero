"""
Suite de Pruebas Funcionales y Unitarias del Chatbot Financiero (Fase 4, RNF01–RNF08).
Verifica:
  1. Las 18 transiciones formales de la Matriz δ (Tabla XI, RNF01).
  2. La conversión exacta de texto decimal a centavos enteros en Python (Tabla XII, RF03).
  3. El flujo conversacional completo y los mensajes de las Figuras 5, 6 y 7 (RF01–RF12).
  4. El aislamiento multiusuario en el AFD y en SQLite.
  5. El rechazo de falsas confirmaciones cuando falla la escritura en SQLite (RF09, RF10).
  6. El módulo /informacion en estado de reposo (S0) y su bloqueo fuera de secuencia en S1/S2.
"""
from pathlib import Path
import pytest
from src.afd import ALFABETO_SIGMA, ESTADOS_Q, MATRIZ_TRANSICIONES, ControladorAFD
from src.bot_telegram import TelegramBotCliente
from src.database import BaseDatosGastos
from src.validador import (
    clasificar_entrada,
    formatear_centavos_a_moneda,
    validar_concepto,
    validar_y_convertir_monto,
)


def test_rnf01_totalidad_y_determinismo_matriz_tabla_xi():
    """RNF01: Verifica que las 18 combinaciones (Q x Σ) existan y coincidan con la Tabla XI."""
    esperado_tabla_xi = {
        ("S0", "c"): "S1", ("S1", "c"): "S1", ("S2", "c"): "S1",
        ("S0", "mv"): "S0", ("S1", "mv"): "S2", ("S2", "mv"): "S2",
        ("S0", "mi"): "S0", ("S1", "mi"): "S1", ("S2", "mi"): "S2",
        ("S0", "tv"): "S0", ("S1", "tv"): "S1", ("S2", "tv"): "S0",
        ("S0", "ti"): "S0", ("S1", "ti"): "S1", ("S2", "ti"): "S2",
        ("S0", "e"): "S0", ("S1", "e"): "S1", ("S2", "e"): "S2",
    }
    assert len(MATRIZ_TRANSICIONES) == len(ESTADOS_Q) * len(ALFABETO_SIGMA) == 18
    for (estado, simbolo), destino_esperado in esperado_tabla_xi.items():
        assert ControladorAFD.evaluar_transicion_pura(estado, simbolo) == destino_esperado


@pytest.mark.parametrize(
    "texto_entrada, centavos_esperados",
    [
        ("15500.00", 1550000),
        ("15500.50", 1550050),
        ("1250.75", 125075),
        ("500", 50000),
        ("0.01", 1),
    ],
)
def test_tabla_xii_conversion_exacta_centavos(texto_entrada: str, centavos_esperados: int):
    """Tabla XII / RF03: Verifica conversión exacta a INTEGER en centavos sin errores IEEE 754."""
    es_valido, centavos = validar_y_convertir_monto(texto_entrada)
    assert es_valido is True
    assert centavos == centavos_esperados
    assert isinstance(centavos, int)


@pytest.mark.parametrize(
    "monto_invalido",
    ["quince mil pesos", "-1500", "0", "0.00", "1500.555", "15,500,00", "", "   ", "abc123"],
)
def test_rf03_rf04_rechazo_montos_invalidos(monto_invalido: str):
    """RF03 / RF04: Verifica que montos no numéricos, negativos, cero o mal formateados se rechacen."""
    es_valido, centavos = validar_y_convertir_monto(monto_invalido)
    assert es_valido is False
    assert centavos is None


def test_rf06_rf07_validacion_concepto():
    """RF06 / RF07 / Fig. 6: Verifica aceptación de conceptos válidos y rechazo de vacíos o '- - -'."""
    assert validar_concepto("Almuerzo ejecutivo") == (True, "Almuerzo ejecutivo")
    assert validar_concepto("") == (False, "")
    assert validar_concepto("    ") == (False, "")
    assert validar_concepto("- - -") == (False, "")


def test_flujo_completo_mockups_fig5_fig6_fig7(tmp_path: Path):
    """
    Simula exactamente las interacciones de las Figuras 5, 6 y 7 del documento IEEE
    y comprueba estados, respuestas y persistencia en SQLite.
    """
    db_test = BaseDatosGastos(db_path=tmp_path / "test_gastos.db")
    bot = TelegramBotCliente(token="TOKEN_PRUEBA", db=db_test)
    uid = 1004915051
    user = "carlos_test"

    # 1. Inicio (/gasto) -> S0 a S1 (Fig. 5)
    r1 = bot.manejar_entrada_usuario(uid, user, "/gasto")
    assert "Iniciando registro de gasto." in r1
    assert bot.afd.obtener_estado(uid) == "S1"

    # 2. Entrada fuera de secuencia en S1 (Fig. 7)
    r_fuera = bot.manejar_entrada_usuario(uid, user, "¿Cuáles son mis reportes del mes?")
    assert "Operación no válida para la etapa actual" in r_fuera
    assert "MONTO" in r_fuera
    assert bot.afd.obtener_estado(uid) == "S1"

    # 3. Monto inválido en S1 (Fig. 5)
    r_mi = bot.manejar_entrada_usuario(uid, user, "quince mil pesos")
    assert "❌ Error: El monto debe ser un valor numérico positivo." in r_mi
    assert bot.afd.obtener_estado(uid) == "S1"

    # 4. Monto válido en S1 -> S2 (Fig. 5)
    r_mv = bot.manejar_entrada_usuario(uid, user, "15500.50")
    assert "Monto aceptado ($15,500.50). Ahora ingresa el concepto del gasto:" in r_mv
    assert bot.afd.obtener_estado(uid) == "S2"
    assert bot.afd.obtener_sesion(uid).monto_centavos == 1550050

    # 5. Concepto inválido '- - -' en S2 -> Conserva S2 y el monto temporal (Fig. 6)
    r_ti = bot.manejar_entrada_usuario(uid, user, "- - -")
    assert "❌ Error: El concepto no puede estar vacío." in r_ti
    assert bot.afd.obtener_estado(uid) == "S2"
    assert bot.afd.obtener_sesion(uid).monto_centavos == 1550050

    # 6. Comando /informacion enviado a mitad de S2 -> Rechazado como fuera de secuencia (RF12)
    r_info_bloqueado = bot.manejar_entrada_usuario(uid, user, "/informacion")
    assert "Operación no válida para la etapa actual" in r_info_bloqueado
    assert bot.afd.obtener_estado(uid) == "S2"
    assert bot.afd.obtener_sesion(uid).monto_centavos == 1550050

    # 7. Concepto válido en S2 -> Guarda en SQLite y vuelve a S0 (Fig. 6)
    r_tv = bot.manejar_entrada_usuario(uid, user, "Almuerzo ejecutivo")
    assert "✅ ¡Gasto registrado exitosamente!" in r_tv
    assert "• Monto: $15,500.50" in r_tv
    assert "• Concepto: Almuerzo ejecutivo" in r_tv
    assert bot.afd.obtener_estado(uid) == "S0"

    # 8. Ahora que está en reposo (S0), /informacion sí muestra el resumen
    r_info_ok = bot.manejar_entrada_usuario(uid, user, "/informacion")
    assert "Estado actual del autómata: S0 (Inactivo / En reposo)" in r_info_ok
    assert "Total de transacciones: 1" in r_info_ok
    assert "$15,500.50" in r_info_ok
    assert "Almuerzo ejecutivo" in r_info_ok


def test_aislamiento_multiusuario_y_prevencion_falsa_confirmacion(tmp_path: Path, monkeypatch):
    """
    Comprueba que dos usuarios concurrentes no mezclen estados ni datos en SQLite,
    y que ante un fallo de base de datos (RF10) no se envíe falsa confirmación.
    """
    db_test = BaseDatosGastos(db_path=tmp_path / "multi_gastos.db")
    bot = TelegramBotCliente(token="TOKEN_PRUEBA", db=db_test)

    u1, u2 = 111, 222
    bot.manejar_entrada_usuario(u1, "user1", "/gasto")
    bot.manejar_entrada_usuario(u1, "user1", "10000")  # u1 queda en S2 con $10,000.00

    bot.manejar_entrada_usuario(u2, "user2", "/gasto")  # u2 apenas va en S1
    assert bot.afd.obtener_estado(u1) == "S2"
    assert bot.afd.obtener_estado(u2) == "S1"

    # u1 guarda su gasto
    bot.manejar_entrada_usuario(u1, "user1", "Taxi")
    assert db_test.obtener_gastos_usuario(u1)["total_registros"] == 1
    assert db_test.obtener_gastos_usuario(u2)["total_registros"] == 0

    # Simular fallo de escritura en SQLite para u2 (RF10)
    bot.manejar_entrada_usuario(u2, "user2", "25000")
    monkeypatch.setattr(db_test, "registrar_gasto", lambda **kwargs: (False, "2026-11-15 12:00", "Disk full"))
    r_fallo = bot.manejar_entrada_usuario(u2, "user2", "Cena")
    assert "❌ Error de almacenamiento" in r_fallo
    assert "¡Gasto registrado exitosamente!" not in r_fallo
    assert bot.afd.obtener_estado(u2) == "S0"
