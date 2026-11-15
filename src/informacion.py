"""
Módulo 6: Consulta de Información en Estado de Reposo (S0) — Comando /informacion.
Permite al usuario consultar la guía del bot y el resumen de sus propios gastos
únicamente cuando el Autómata Finito Determinista se encuentra en reposo (S0).
"""
from src.database import BaseDatosGastos
from src.validador import formatear_centavos_a_moneda


def generar_mensaje_informacion(db: BaseDatosGastos, id_usuario: int, nombre_usuario: str) -> str:
    """
    Construye el reporte informativo y el resumen financiero personal del usuario
    cuando el AFD está en el estado S0 (Inactivo).
    """
    datos = db.obtener_gastos_usuario(id_usuario=id_usuario, limite=5)
    total_registros = datos["total_registros"]
    total_formateado = formatear_centavos_a_moneda(datos["suma_centavos"])
    ultimos = datos["ultimos_gastos"]

    lineas = [
        "ℹ️ Información del Chatbot Financiero (AFD)",
        f"• Usuario: @{nombre_usuario}",
        "• Estado actual del autómata: S0 (Inactivo / En reposo)",
        "",
        "📌 Comandos disponibles:",
        "  • /gasto — Iniciar el registro secuencial de un gasto",
        "  • /informacion — Ver esta guía y tu resumen de gastos (solo en reposo)",
        "  • /cancelar — Cancelar un registro en curso y volver a S0",
        "",
        "📊 Resumen de tus gastos registrados:",
        f"• Total de transacciones: {total_registros}",
        f"• Monto total acumulado: {total_formateado}",
    ]

    if ultimos:
        lineas.append("• Últimos gastos registrados:")
        for idx, g in enumerate(ultimos, start=1):
            monto_str = formatear_centavos_a_moneda(g["monto"])
            lineas.append(f"  {idx}. {monto_str} — {g['concepto']} ({g['fecha_hora']})")
    else:
        lineas.append("• Aún no tienes gastos registrados. ¡Envía /gasto para registrar el primero!")

    return "\n".join(lineas)
