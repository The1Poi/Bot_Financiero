"""
Módulo 5: Configuración y Ejecución (RF14, RNF03).
Carga las variables de entorno desde el archivo local .env y descifra en memoria
cualquier secreto protegido con ENC[DPAPI_FERNET:...] usando Windows Credential Manager,
manteniendo intacta la lectura mediante os.environ / os.getenv.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from proteger_env import descifrar_valor, PREFIX

# Ruta base del proyecto (Bot_Financiero/)
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# 1. Cargar variables de entorno desde .env hacia os.environ
load_dotenv(dotenv_path=ENV_PATH)

# 2. Si TELEGRAM_BOT_TOKEN está cifrado en .env, descifrarlo en memoria e inyectarlo en os.environ
_raw_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
if _raw_token.startswith(PREFIX):
    os.environ["TELEGRAM_BOT_TOKEN"] = descifrar_valor(_raw_token)

# 3. Exponer variables igual que antes (os.getenv / os.environ siguen funcionando en toda la app)
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "gastos.db")).strip()


def validar_configuracion() -> None:
    """Verifica que el token del bot esté configurado antes de iniciar (RF14)."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "tu_token_de_telegram_aqui":
        raise RuntimeError(
            "Error de configuración (RF14): No se encontró un TELEGRAM_BOT_TOKEN válido en el archivo .env."
        )
