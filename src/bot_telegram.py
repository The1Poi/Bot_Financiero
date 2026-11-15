"""
Módulo 1: Interfaz y Mensajería (RF13).
Conecta con la Bot API de Telegram mediante HTTPS Long Polling.
Configuración básica inicial: responde 'Hola mundo mundano' al comando /start.
"""
import time
import requests
from src.config import TELEGRAM_BOT_TOKEN, validar_configuracion


class TelegramBotCliente:
    """Cliente HTTP de Long Polling para la Bot API de Telegram."""

    def __init__(self, token: str):
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.session = requests.Session()
        self.offset = 0

    def verificar_conexion(self) -> dict:
        """Comprueba que el token sea válido consultando el método getMe."""
        resp = self.session.get(f"{self.base_url}/getMe", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Respuesta inválida de Telegram: {data}")
        return data["result"]

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

    def procesar_mensaje(self, mensaje: dict) -> None:
        """Procesa un mensaje entrante de Telegram."""
        chat = mensaje.get("chat", {})
        chat_id = chat.get("id")
        texto = (mensaje.get("text") or "").strip()
        usuario = mensaje.get("from", {}).get("username") or mensaje.get("from", {}).get("first_name", "Usuario")

        if not chat_id or not texto:
            return

        print(f"[Mensaje recibido] De @{usuario} (chat_id={chat_id}): {texto}")

        # Respuesta básica para /start solicitada en la prueba inicial
        if texto.lower().startswith("/start"):
            respuesta = "Hola mundo mundano"
            self.enviar_mensaje(chat_id, respuesta)
            print(f"[Respuesta enviada] A @{usuario}: {respuesta}")

    def iniciar_polling(self) -> None:
        """Inicia el bucle principal de recepción de mensajes (CU06)."""
        validar_configuracion()
        info_bot = self.verificar_conexion()
        print("============================================================")
        print(f"Bot conectado exitosamente: @{info_bot.get('username')} ({info_bot.get('first_name')})")
        print("Escuchando mensajes vía HTTPS Long Polling... (Presiona Ctrl+C para detener)")
        print("Envía /start desde Telegram para recibir 'Hola mundo mundano'.")
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
