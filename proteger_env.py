"""
Utilidad de seguridad para el Grupo 1 (RF14, RNF03):
Combina derivación de clave por contraseña compartida del equipo (PBKDF2-HMAC-SHA256, 480,000 iteraciones)
+ Cifrado autenticado Fernet (AES-128-CBC + HMAC-SHA256) en el archivo .env
+ Caché seguro de la llave derivada en Windows Credential Manager (DPAPI) vía keyring
  (con soporte multiplataforma automático para servidores Linux como PythonAnywhere).

Comandos principales para los 4 integrantes del equipo:
  1. Configurar la clave del equipo en un PC o servidor nuevo (1 sola vez):
     python proteger_env.py --unlock
  2. Cifrar un token en texto plano dentro de .env:
     python proteger_env.py --encrypt
  3. Cambiar/rotar el token de Telegram y dejarlo cifrado:
     python proteger_env.py --rotate
  4. Ver/descifrar el token en consola (requiere confirmar la clave del equipo):
     python proteger_env.py --decrypt
  5. Verificar que .env está cifrado y listo para usarse:
     python proteger_env.py --verify
"""
import argparse
import base64
import getpass
import os
import re
from pathlib import Path
import keyring
from keyring.errors import KeyringError, NoKeyringError
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SERVICE_NAME = "Bot_Financiero_Unipamplona"
KEY_ACCOUNT = "ENV_TEAM_KEY_G1"
PROJECT_SALT = b"Unipamplona_TeoriaComp_Grupo1_2026_Salt"
PBKDF2_ITERATIONS = 480_000

PREFIX = "ENC[DPAPI_FERNET:"
SUFFIX = "]"

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
LINUX_FALLBACK_KEY_FILE = Path.home() / ".config" / "bot_financiero_g1" / "team.key"


def derivar_llave_desde_clave_equipo(clave_equipo: str) -> str:
    """
    Deriva determinísticamente una llave Fernet de 32 bytes (URL-safe Base64)
    a partir de la clave secreta del Grupo 1 usando PBKDF2-HMAC-SHA256.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=PROJECT_SALT,
        iterations=PBKDF2_ITERATIONS,
    )
    key_bytes = base64.urlsafe_b64encode(kdf.derive(clave_equipo.strip().encode("utf-8")))
    return key_bytes.decode("utf-8")


def guardar_clave_equipo_en_dpapi(clave_equipo: str | None = None) -> str:
    """
    Pide la clave secreta del Grupo 1, deriva la llave criptográfica y la almacena
    en Windows Credential Manager (DPAPI) o en almacén restringido del usuario en Linux.
    """
    if not clave_equipo:
        clave_equipo = getpass.getpass("Ingresa la clave secreta del Grupo 1: ").strip()
    if not clave_equipo:
        raise ValueError("La clave secreta del equipo no puede estar vacía.")

    llave_derivada = derivar_llave_desde_clave_equipo(clave_equipo)
    try:
        keyring.set_password(SERVICE_NAME, KEY_ACCOUNT, llave_derivada)
        print(f"[OK] Llave del Grupo 1 derivada y guardada en el llavero del sistema ({SERVICE_NAME}).")
    except (NoKeyringError, KeyringError):
        LINUX_FALLBACK_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        LINUX_FALLBACK_KEY_FILE.write_text(llave_derivada, encoding="utf-8")
        try:
            os.chmod(LINUX_FALLBACK_KEY_FILE, 0o600)
        except OSError:
            pass
        print(f"[OK] Llave del Grupo 1 guardada en almacén privado de Linux ({LINUX_FALLBACK_KEY_FILE}).")
    return llave_derivada


def obtener_llave_desde_dpapi() -> str:
    """Recupera la llave derivada desde Windows Credential Manager, variable de entorno o almacén Linux."""
    # 1. Si se definió BOT_TEAM_PASSPHRASE en variables de entorno del servidor
    env_pass = os.environ.get("BOT_TEAM_PASSPHRASE", "").strip()
    if env_pass:
        return derivar_llave_desde_clave_equipo(env_pass)

    # 2. Intentar desde Windows Credential Manager / Keyring del SO
    try:
        llave = keyring.get_password(SERVICE_NAME, KEY_ACCOUNT)
        if llave:
            return llave
    except (NoKeyringError, KeyringError):
        pass

    # 3. Fallback para servidores Linux sin GUI (ej. PythonAnywhere)
    if LINUX_FALLBACK_KEY_FILE.exists():
        llave = LINUX_FALLBACK_KEY_FILE.read_text(encoding="utf-8").strip()
        if llave:
            return llave

    raise RuntimeError(
        "Este entorno aún no tiene desbloqueada la llave del Grupo 1.\n"
        "Ejecuta primero: python proteger_env.py --unlock"
    )


def cifrar_valor(valor_plano: str, llave_fernet: str) -> str:
    """Cifra un texto plano y lo devuelve con el formato ENC[DPAPI_FERNET:...]."""
    f = Fernet(llave_fernet.encode("utf-8"))
    token_cifrado = f.encrypt(valor_plano.strip().encode("utf-8")).decode("utf-8")
    return f"{PREFIX}{token_cifrado}{SUFFIX}"


def descifrar_valor(valor_env: str, llave_fernet: str | None = None) -> str:
    """
    Si el valor tiene el prefijo ENC[DPAPI_FERNET:...], usa la llave del Grupo 1
    y devuelve el secreto en texto plano (solo en memoria).
    """
    valor_env = valor_env.strip()
    if not (valor_env.startswith(PREFIX) and valor_env.endswith(SUFFIX)):
        return valor_env

    token_cifrado = valor_env[len(PREFIX) : -len(SUFFIX)]
    llave = llave_fernet or obtener_llave_desde_dpapi()
    try:
        f = Fernet(llave.encode("utf-8"))
        return f.decrypt(token_cifrado.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError(
            "Error al descifrar TELEGRAM_BOT_TOKEN: la clave del equipo no coincide con la que cifró el archivo .env."
        ) from exc


def cifrar_env_actual(clave_equipo: str | None = None) -> None:
    """Cifra el TELEGRAM_BOT_TOKEN de .env usando la llave del Grupo 1."""
    if not ENV_PATH.exists():
        raise FileNotFoundError(f"No existe el archivo {ENV_PATH}")

    llave = guardar_clave_equipo_en_dpapi(clave_equipo) if clave_equipo else obtener_llave_desde_dpapi()
    lineas = ENV_PATH.read_text(encoding="utf-8").splitlines()
    nuevas_lineas = []
    cifrado = False

    for linea in lineas:
        if linea.strip().startswith("TELEGRAM_BOT_TOKEN="):
            _, valor = linea.split("=", 1)
            valor = valor.strip()
            if valor.startswith(PREFIX):
                print("[INFO] TELEGRAM_BOT_TOKEN ya está cifrado en .env.")
                nuevas_lineas.append(linea)
            else:
                valor_cifrado = cifrar_valor(valor, llave)
                nuevas_lineas.append(f"TELEGRAM_BOT_TOKEN={valor_cifrado}")
                cifrado = True
        else:
            nuevas_lineas.append(linea)

    if cifrado:
        ENV_PATH.write_text("\n".join(nuevas_lineas) + "\n", encoding="utf-8")
        print("[OK] TELEGRAM_BOT_TOKEN cifrado exitosamente en .env con la llave del Grupo 1.")


def rotar_o_recifrar_token(nuevo_token: str | None = None, clave_equipo: str | None = None) -> None:
    """Cifra un nuevo token (o recifra el especificado) con la clave del Grupo 1."""
    llave = guardar_clave_equipo_en_dpapi(clave_equipo) if clave_equipo else obtener_llave_desde_dpapi()
    if not nuevo_token:
        nuevo_token = getpass.getpass("Ingresa el TELEGRAM_BOT_TOKEN en texto plano a cifrar (oculto): ").strip()
    if not nuevo_token:
        raise ValueError("El token no puede estar vacío.")

    valor_cifrado = cifrar_valor(nuevo_token, llave)

    if ENV_PATH.exists():
        contenido = ENV_PATH.read_text(encoding="utf-8")
        if re.search(r"^TELEGRAM_BOT_TOKEN=.*$", contenido, flags=re.MULTILINE):
            nuevo_contenido = re.sub(
                r"^TELEGRAM_BOT_TOKEN=.*$",
                f"TELEGRAM_BOT_TOKEN={valor_cifrado}",
                contenido,
                flags=re.MULTILINE,
            )
        else:
            nuevo_contenido = contenido.rstrip() + f"\nTELEGRAM_BOT_TOKEN={valor_cifrado}\n"
    else:
        nuevo_contenido = f"TELEGRAM_BOT_TOKEN={valor_cifrado}\nSQLITE_DB_PATH=gastos.db\n"

    ENV_PATH.write_text(nuevo_contenido, encoding="utf-8")
    print("[OK] TELEGRAM_BOT_TOKEN cifrado en .env con la clave secreta del Grupo 1.")


def mostrar_token_descifrado(clave_equipo: str | None = None) -> None:
    """Descifra y muestra el token en consola tras validar la clave secreta del Grupo 1."""
    if not ENV_PATH.exists():
        print("[ERROR] No existe el archivo .env")
        return

    if not clave_equipo:
        clave_equipo = getpass.getpass("Ingresa la clave secreta del Grupo 1 para ver el token: ").strip()
    llave = derivar_llave_desde_clave_equipo(clave_equipo)

    for linea in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if linea.strip().startswith("TELEGRAM_BOT_TOKEN="):
            _, valor = linea.split("=", 1)
            token_plano = descifrar_valor(valor.strip(), llave_fernet=llave)
            print(f"[TOKEN DESCIFRADO]: {token_plano}")
            return
    print("[ERROR] No se encontró TELEGRAM_BOT_TOKEN en .env")


def verificar_estado() -> None:
    """Comprueba que .env tenga el token cifrado y que pueda desencriptarse en memoria."""
    if not ENV_PATH.exists():
        print("[ERROR] No existe el archivo .env")
        return

    for linea in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if linea.strip().startswith("TELEGRAM_BOT_TOKEN="):
            _, valor = linea.split("=", 1)
            valor = valor.strip()
            es_cifrado = valor.startswith(PREFIX) and valor.endswith(SUFFIX)
            print(f"1. Valor en disco (.env): {valor[:42]}...{valor[-10:] if len(valor) > 52 else ''}")
            print(f"2. ¿Está cifrado en disco?: {'SÍ' if es_cifrado else 'NO (TEXTO PLANO)'}")
            token_plano = descifrar_valor(valor)
            enmascarado = f"{token_plano[:6]}...{token_plano[-4:]}" if len(token_plano) > 12 else "***"
            print(f"3. Descifrado en memoria (Grupo 1): OK ({enmascarado})")
            return
    print("[ERROR] No se encontró la variable TELEGRAM_BOT_TOKEN en .env")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gestor de secretos en .env para el Grupo 1 (PBKDF2 + Fernet + DPAPI)")
    parser.add_argument("--unlock", action="store_true", help="Desbloquea y guarda la clave del Grupo 1 en este equipo")
    parser.add_argument("--encrypt", "--migrate", action="store_true", dest="encrypt", help="Cifra el token en texto plano que esté en .env")
    parser.add_argument("--rotate", action="store_true", help="Pide un nuevo token en consola y lo cifra en .env")
    parser.add_argument("--decrypt", action="store_true", help="Muestra el token en texto plano tras pedir la clave del Grupo 1")
    parser.add_argument("--verify", action="store_true", help="Verifica que el .env cifrado se descifre correctamente")
    parser.add_argument("--passphrase", type=str, help="Pasa la clave del Grupo 1 por argumento (opcional)")
    parser.add_argument("--token", type=str, help="Pasa el token por argumento para --rotate (opcional)")
    args = parser.parse_args()

    if args.unlock:
        guardar_clave_equipo_en_dpapi(args.passphrase)
        if ENV_PATH.exists():
            verificar_estado()
    elif args.rotate:
        rotar_o_recifrar_token(nuevo_token=args.token, clave_equipo=args.passphrase)
        verificar_estado()
    elif args.decrypt:
        mostrar_token_descifrado(clave_equipo=args.passphrase)
    elif args.encrypt:
        cifrar_env_actual(clave_equipo=args.passphrase)
        verificar_estado()
    else:
        verificar_estado()
