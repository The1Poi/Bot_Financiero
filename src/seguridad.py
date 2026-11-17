"""
Módulo de Seguridad Anti-Bot y Anti-Flood (Protección de Dos Niveles).
Mitiga:
  1. Envío masivo de mensajes (Inbound Rate Limiting por ventana deslizante).
  2. Repetición abusiva del mismo fallo o errores consecutivos (Anti-Loop / Anti-Spam).
  3. Mensajes que no deben procesarse ni recibir respuesta (otros bots, chats no privados,
     contenido multimedia sin texto, o payloads gigantes > 500 caracteres).
"""
import time
from collections import deque
from dataclasses import dataclass, field


MAX_RAW_MESSAGE_CHARS = 500  # Límite duro previo a regex para evitar saturación/ReDoS
FLOOD_MAX_MENSAJES = 5       # Máximo de mensajes permitidos en la ventana
FLOOD_VENTANA_SEG = 10.0     # Ventana deslizante en segundos
FLOOD_COOLDOWN_SEG = 30.0    # Tiempo de bloqueo temporal tras flood

MAX_FALLOS_REPETIDOS = 4     # Máximo de fallos repetidos consecutivos antes de enfriamiento
FALLO_COOLDOWN_SEG = 20.0    # Tiempo de enfriamiento tras repetir el mismo error


@dataclass
class EstadoSeguridadUsuario:
    """Registro de actividad y bloqueos temporales aislado por id_usuario."""
    timestamps: deque[float] = field(default_factory=deque)
    bloqueado_hasta: float = 0.0
    aviso_bloqueo_enviado: bool = False
    ultimo_error_texto: str = ""
    conteo_mismo_error: int = 0


class ProtectorAntiBot:
    """
    Capa de defensa previa al Motor AFD.
    Evalúa si un mensaje entrante de Telegram es legítimo o debe ser bloqueado/silenciado.
    """

    def __init__(
        self,
        max_mensajes: int = FLOOD_MAX_MENSAJES,
        ventana_seg: float = FLOOD_VENTANA_SEG,
        cooldown_flood_seg: float = FLOOD_COOLDOWN_SEG,
        max_fallos_repetidos: int = MAX_FALLOS_REPETIDOS,
        cooldown_fallo_seg: float = FALLO_COOLDOWN_SEG,
        max_raw_chars: int = MAX_RAW_MESSAGE_CHARS,
    ) -> None:
        self.max_mensajes = max_mensajes
        self.ventana_seg = ventana_seg
        self.cooldown_flood_seg = cooldown_flood_seg
        self.max_fallos_repetidos = max_fallos_repetidos
        self.cooldown_fallo_seg = cooldown_fallo_seg
        self.max_raw_chars = max_raw_chars
        self._usuarios: dict[int, EstadoSeguridadUsuario] = {}

    def _obtener_estado(self, id_usuario: int) -> EstadoSeguridadUsuario:
        if id_usuario not in self._usuarios:
            self._usuarios[id_usuario] = EstadoSeguridadUsuario()
        return self._usuarios[id_usuario]

    @staticmethod
    def es_mensaje_procesable(mensaje: dict) -> tuple[bool, str]:
        """
        Filtra mensajes que no tendrán respuesta (descarte silencioso):
          - Mensajes enviados por otros bots (is_bot=True).
          - Mensajes fuera de chats privados (grupos, supergrupos, canales).
          - Actualizaciones sin texto (stickers, audios, fotos, documentos).
        """
        remitente = mensaje.get("from") or {}
        if remitente.get("is_bot", False):
            return False, "ignorado_es_bot"

        chat = mensaje.get("chat") or {}
        chat_type = chat.get("type", "private")
        if chat_type != "private":
            return False, "ignorado_chat_no_privado"

        texto = mensaje.get("text")
        if not isinstance(texto, str) or not texto.strip():
            return False, "ignorado_sin_texto"

        return True, "ok"

    def verificar_rate_limit_y_tamano(
        self, id_usuario: int, texto: str, ahora: float | None = None
    ) -> tuple[bool, str | None]:
        """
        Evalúa límite de tamaño del payload y tasa de envío (Inbound Rate Limiting).

        Retorna:
            (permitido, mensaje_advertencia_opcional)
            - Si permitido == False y mensaje_advertencia_opcional is None -> descartar en silencio.
            - Si permitido == False y mensaje_advertencia_opcional is not None -> enviar única advertencia.
        """
        ts = ahora if ahora is not None else time.monotonic()
        estado = self._obtener_estado(id_usuario)

        # 1. Si el usuario está actualmente en cooldown, descartar en silencio
        if ts < estado.bloqueado_hasta:
            if not estado.aviso_bloqueo_enviado:
                estado.aviso_bloqueo_enviado = True
                restante = int(max(1, round(estado.bloqueado_hasta - ts)))
                return (
                    False,
                    f"⏳ Demasiados mensajes seguidos. Por seguridad, espera {restante} segundos antes de continuar.",
                )
            return False, None

        # Reiniciar bandera si ya expiró el cooldown
        estado.aviso_bloqueo_enviado = False

        # 2. Limpiar marcas de tiempo fuera de la ventana deslizante
        while estado.timestamps and (ts - estado.timestamps[0]) > self.ventana_seg:
            estado.timestamps.popleft()

        estado.timestamps.append(ts)

        # 3. Verificar flood (envío masivo en pocos segundos)
        if len(estado.timestamps) > self.max_mensajes:
            estado.bloqueado_hasta = ts + self.cooldown_flood_seg
            estado.aviso_bloqueo_enviado = True
            return (
                False,
                f"⏳ Has enviado demasiados mensajes en poco tiempo. Espera {int(self.cooldown_flood_seg)} segundos.",
            )

        # 4. Protección contra payloads gigantes (ej. 1 millón de caracteres) antes de pasar a regex/AFD
        if len(texto) > self.max_raw_chars:
            return (
                False,
                f"⚠️ Mensaje demasiado largo ({len(texto)} caracteres). "
                f"El límite máximo permitido por mensaje es de {self.max_raw_chars} caracteres.",
            )

        return True, None

    def registrar_resultado_afd(
        self, id_usuario: int, es_error: bool, texto_entrada: str, ahora: float | None = None
    ) -> str | None:
        """
        Detecta repetición abusiva del mismo fallo múltiples veces seguidas.
        Si alcanza max_fallos_repetidos, activa un cooldown y devuelve una advertencia final;
        si el mensaje es válido, reinicia el contador.
        """
        ts = ahora if ahora is not None else time.monotonic()
        estado = self._obtener_estado(id_usuario)

        if not es_error:
            estado.ultimo_error_texto = ""
            estado.conteo_mismo_error = 0
            return None

        entrada_norm = texto_entrada.strip().lower()
        if entrada_norm == estado.ultimo_error_texto:
            estado.conteo_mismo_error += 1
        else:
            estado.ultimo_error_texto = entrada_norm
            estado.conteo_mismo_error = 1

        if estado.conteo_mismo_error >= self.max_fallos_repetidos:
            estado.bloqueado_hasta = ts + self.cooldown_fallo_seg
            estado.aviso_bloqueo_enviado = True
            estado.conteo_mismo_error = 0
            return (
                f"🛑 Has repetido el mismo fallo {self.max_fallos_repetidos} veces seguidas. "
                f"El bot pausará tus respuestas por {int(self.cooldown_fallo_seg)} segundos. "
                "Cuando se reanude, verifica el formato o envía /cancelar."
            )

        return None
