"""
Módulo 1: Interfaz y Mensajería con Telegram Bot API (RF13, RNF04, RNF06).
Integra el cliente HTTPS Long Polling con el Motor Formal del AFD (src/afd.py),
el Validador (src/validador.py), la Persistencia SQLite (src/database.py),
el Módulo de Información en reposo (src/informacion.py) y el menú interactivo '/' (setMyCommands).
"""
import time
import requests
from src.afd import ControladorAFD
from src.config import TELEGRAM_BOT_TOKEN, validar_configuracion
from src.database import BaseDatosGastos
from src.informacion import generar_mensaje_informacion
from src.validador import (
    clasificar_entrada,
    formatear_centavos_a_moneda,
    validar_concepto,
    validar_y_convertir_monto,
)

# Comandos que aparecen automáticamente en Telegram al presionar '/' o el botón de menú
COMANDOS_MENU_TELEGRAM = [
    {"command": "gasto", "description": "Iniciar registro secuencial de un gasto"},
    {"command": "informacion", "description": "Ver resumen de tus gastos y guía (en reposo)"},
    {"command": "cancelar", "description": "Cancelar el registro actual y volver a inactivo"},
    {"command": "start", "description": "Iniciar el chatbot financiero"},
]


class TelegramBotCliente:
    """Cliente HTTP de Long Polling conectado al Autómata Finito Determinista (AFD)."""

    def __init__(self, token: str, db: BaseDatosGastos | None = None) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.session = requests.Session()
        self.offset = 0
        self.afd = ControladorAFD()
        self.db = db if db is not None else BaseDatosGastos()

    def verificar_conexion(self) -> dict:
        """Comprueba que el token sea válido consultando el método getMe."""
        resp = self.session.get(f"{self.base_url}/getMe", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Respuesta inválida de Telegram: {data}")
        return data["result"]

    def configurar_menu_comandos(self) -> None:
        """
        Registra la lista de comandos en Telegram (setMyCommands y setChatMenuButton)
        para que al escribir '/' o tocar el botón azul aparezca el menú desplegable.
        """
        try:
            self.session.post(
                f"{self.base_url}/setMyCommands",
                json={"commands": COMANDOS_MENU_TELEGRAM},
                timeout=10,
            )
            self.session.post(
                f"{self.base_url}/setChatMenuButton",
                json={"menu_button": {"type": "commands"}},
                timeout=10,
            )
            print("[OK] Menú interactivo de comandos ('/') configurado en Telegram.")
        except requests.RequestException as exc:
            print(f"[Advertencia] No se pudo actualizar el menú de comandos: {exc}")

    def obtener_actualizaciones(self, timeout: int = 25) -> list:
        """Solicita nuevos mensajes mediante HTTPS Long Polling (getUpdates)."""
        params = {"offset": self.offset, "timeout": timeout}
        resp = self.session.get(
            f"{self.base_url}/getUpdates", params=params, timeout=timeout + 5
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])

    def enviar_mensaje(self, chat_id: int, texto: str) -> None:
        """Envía un mensaje de texto al chat indicado (sendMessage)."""
        payload = {"chat_id": chat_id, "text": texto}
        resp = self.session.post(f"{self.base_url}/sendMessage", json=payload, timeout=10)
        resp.raise_for_status()

    def manejar_entrada_usuario(
        self, id_usuario: int, nombre_usuario: str, texto: str
    ) -> str:
        """
        Procesa el texto enviado por un usuario según su estado actual en el AFD
        y retorna el mensaje exacto de respuesta (cumpliendo Fig. 5, 6 y 7 del documento IEEE).
        """
        limpio = (texto or "").strip()
        comando_base = limpio.split()[0].lower().split("@")[0] if limpio else ""
        estado_actual = self.afd.obtener_estado(id_usuario)

        # 1. Soporte para /cancelar (mostrado en el mockup de la Fig. 7)
        if comando_base == "/cancelar":
            self.afd.cancelar_flujo(id_usuario)
            return (
                "🛑 Operación cancelada. El sistema ha retornado al estado inactivo (S0).\n"
                "Envía /gasto cuando desees iniciar un nuevo registro o /informacion para ver tu resumen."
            )

        # 2. Soporte en estado de reposo (S0) para /start y /informacion
        if estado_actual == "S0":
            if comando_base == "/start":
                return (
                    "Hola mundo mundano 👋\n"
                    "Bienvenido al Chatbot Financiero basado en un Autómata Finito Determinista (AFD).\n\n"
                    "• Usa /gasto para iniciar el registro secuencial de un gasto.\n"
                    "• Usa /informacion para consultar tus gastos registrados.\n"
                    "• Usa /cancelar si deseas abortar un registro en curso."
                )
            if comando_base == "/informacion":
                return generar_mensaje_informacion(self.db, id_usuario, nombre_usuario)

        # 3. Clasificación formal de la entrada en el alfabeto Σ = {c, mv, mi, tv, ti, e}
        simbolo = clasificar_entrada(estado_actual, limpio)

        # --- Caso A: Estado actual S0 (Inactivo) ---
        if estado_actual == "S0":
            if simbolo == "c":
                self.afd.aplicar_transicion(id_usuario, "c")
                # Texto exacto de la Fig. 5 (RF01, RF02)
                return (
                    "Iniciando registro de gasto.\n"
                    "Por favor, ingresa el monto (ej. 15500.50):"
                )
            # Cualquier otra entrada en S0 conserva S0 (Tabla XI)
            self.afd.aplicar_transicion(id_usuario, simbolo)
            return (
                "⚠️ No hay un registro de gasto activo en este momento (Estado: S0 Inactivo).\n"
                "Por favor, selecciona /gasto para iniciar un registro o /informacion para ver tu resumen."
            )

        # --- Caso B: Estado actual S1 (Esperando Monto) ---
        if estado_actual == "S1":
            if simbolo == "c":
                self.afd.aplicar_transicion(id_usuario, "c")
                return (
                    "Iniciando registro de gasto.\n"
                    "Por favor, ingresa el monto (ej. 15500.50):"
                )
            if simbolo == "mv":
                _, centavos = validar_y_convertir_monto(limpio)
                self.afd.aplicar_transicion(id_usuario, "mv", monto_centavos=centavos)
                monto_fmt = formatear_centavos_a_moneda(centavos or 0)
                # Texto exacto de las Fig. 5 y 6 (RF05)
                return f"Monto aceptado ({monto_fmt}). Ahora ingresa el concepto del gasto:"
            if simbolo == "mi":
                self.afd.aplicar_transicion(id_usuario, "mi")
                # Texto exacto de la Fig. 5 (RF04, RNF04)
                return "❌ Error: El monto debe ser un valor numérico positivo. Intenta de nuevo:"

            # Símbolo 'e' (Fuera de secuencia en S1 - ej. "¿Cuáles son mis reportes del mes?" o /informacion)
            self.afd.aplicar_transicion(id_usuario, "e")
            # Texto exacto de la Fig. 7 (RF12, RNF04)
            return (
                "⚠️ Operación no válida para la etapa actual.\n"
                "El sistema está esperando que ingreses el MONTO del gasto.\n"
                "Si deseas cancelar, escribe /cancelar."
            )

        # --- Caso C: Estado actual S2 (Esperando Concepto) ---
        if estado_actual == "S2":
            if simbolo == "c":
                self.afd.aplicar_transicion(id_usuario, "c")
                return (
                    "Iniciando registro de gasto.\n"
                    "Por favor, ingresa el monto (ej. 15500.50):"
                )
            if simbolo == "ti":
                self.afd.aplicar_transicion(id_usuario, "ti")
                # Texto exacto de la Fig. 6 (RF07, RNF04)
                return "❌ Error: El concepto no puede estar vacío. Por favor escribe un detalle válido:"
            if simbolo == "tv":
                _, concepto_limpio = validar_concepto(limpio)
                sesion = self.afd.obtener_sesion(id_usuario)
                monto_centavos = sesion.monto_centavos or 0

                # Transición formal S2 --(tv)--> S0 (Inicia I/O en SQLite - Tabla XI)
                self.afd.aplicar_transicion(id_usuario, "tv")

                # Operación externa de persistencia (RF08, RF09, RF10)
                exito, fecha_hora, _ = self.db.registrar_gasto(
                    id_usuario=id_usuario,
                    username_telegram=nombre_usuario,
                    monto_centavos=monto_centavos,
                    concepto=concepto_limpio,
                )
                sesion.monto_centavos = None

                if exito:
                    monto_fmt = formatear_centavos_a_moneda(monto_centavos)
                    # Texto exacto de la Fig. 6 (RF09, RF11)
                    return (
                        "✅ ¡Gasto registrado exitosamente!\n\n"
                        f"• Monto: {monto_fmt}\n"
                        f"• Concepto: {concepto_limpio}\n"
                        f"• Fecha: {fecha_hora}"
                    )
                # Si la escritura en SQLite falla, jamás confirma falsamente (RF10, RF11)
                return (
                    "❌ Error de almacenamiento: No fue posible guardar el gasto en la base de datos local. "
                    "La operación no fue confirmada. El sistema ha retornado al estado inactivo (S0)."
                )

            # Símbolo 'e' (Fuera de secuencia en S2 - conserva estado S2 y monto temporal intacto, RF12)
            self.afd.aplicar_transicion(id_usuario, "e")
            return (
                "⚠️ Operación no válida para la etapa actual.\n"
                "El sistema está esperando que ingreses el CONCEPTO del gasto (ej. Almuerzo ejecutivo).\n"
                "Si deseas cancelar, escribe /cancelar."
            )

        return "⚠️ Estado no reconocido."

    def procesar_mensaje(self, mensaje: dict) -> None:
        """Extrae metadatos del mensaje de Telegram, ejecuta el AFD y envía la respuesta."""
        chat = mensaje.get("chat", {})
        chat_id = chat.get("id")
        remitente = mensaje.get("from", {})
        id_usuario = remitente.get("id") or chat_id
        nombre_usuario = (
            remitente.get("username")
            or remitente.get("first_name")
            or f"usuario_{id_usuario}"
        )
        texto = (mensaje.get("text") or "").strip()

        if not chat_id or not id_usuario or not texto:
            return

        estado_previo = self.afd.obtener_estado(id_usuario)
        respuesta = self.manejar_entrada_usuario(id_usuario, nombre_usuario, texto)
        estado_posterior = self.afd.obtener_estado(id_usuario)

        self.enviar_mensaje(chat_id, respuesta)
        print(
            f"[AFD] @{nombre_usuario} (id={id_usuario}) | '{texto}' | {estado_previo} -> {estado_posterior}"
        )

    def iniciar_polling(self) -> None:
        """Inicia el bucle principal de recepción de mensajes (CU06)."""
        validar_configuracion()
        info_bot = self.verificar_conexion()
        self.configurar_menu_comandos()
        print("============================================================")
        print(f"Bot conectado exitosamente: @{info_bot.get('username')} ({info_bot.get('first_name')})")
        print("Motor AFD activo (Estados: S0 Inactivo, S1 Monto, S2 Concepto) + SQLite local.")
        print("Comandos disponibles en el menú '/': /gasto, /informacion, /cancelar, /start")
        print("============================================================")

        while True:
            try:
                actualizaciones = self.obtener_actualizaciones(timeout=20)
                for upd in actualizaciones:
                    self.offset = upd["update_id"] + 1
                    if "message" in upd:
                        self.procesar_mensaje(upd["message"])
            except KeyboardInterrupt:
                print("\n[Bot detenido por el administrador]")
                break
            except requests.RequestException as exc:
                print(f"[Advertencia de red] Error al consultar Telegram API: {exc}. Reintentando en 3s...")
                time.sleep(3)
            except Exception as exc:
                print(f"[Error inesperado] {exc}")
                time.sleep(2)


def ejecutar_bot() -> None:
    bot = TelegramBotCliente(TELEGRAM_BOT_TOKEN)
    bot.iniciar_polling()
