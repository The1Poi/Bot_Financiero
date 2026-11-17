# Chatbot Financiero basado en un Autómata Finito Determinista (AFD)

Este repositorio contiene el desarrollo de un prototipo funcional de chatbot financiero para **Telegram**, diseñado para agilizar el registro secuencial de gastos personales eliminando la fricción de los formularios tradicionales mediante una interfaz conversacional de flujo estricto.

El núcleo de la solución se fundamenta en la **Teoría de la Computación**, implementando un **Autómata Finito Determinista** $M = (Q, \Sigma, \delta, q_0, F)$ que gobierna el diálogo a través de tres estados explícitos: *Inactivo* ($S_0$), *Esperando Monto* ($S_1$) y *Esperando Concepto* ($S_2$). Este modelo matemático garantiza que cada etapa admita únicamente entradas sintáctica y semánticamente válidas, rechazando entradas fuera de secuencia sin corromper el estado actual ni los datos temporales.

---

## Arquitectura Modular

```text
Bot_Financiero/
├── src/
│   ├── config.py          # Módulo 5: Carga .env y descifra secretos en memoria (RF14, RNF03)
│   ├── validador.py       # Módulo 3: Validación sintáctica/semántica y conversión a centavos (RF03, RF06, Tabla XII)
│   ├── afd.py             # Módulo 2: Motor formal del AFD y Matriz de Transiciones δ (RF01-RF12, RNF01, Tabla XI)
│   ├── database.py        # Módulo 4: Persistencia SQLite parametrizada (USUARIO 1:N GASTO, RF08-RF10, RNF02)
│   ├── informacion.py     # Módulo 6: Consulta de guía y resumen de gastos en reposo S0 (/informacion)
│   └── bot_telegram.py    # Módulo 1: Cliente HTTPS Long Polling y menú '/' de Telegram (RF13, RNF04, RNF06)
├── tests/
│   └── test_matriz_afd.py # Suite de pruebas unitarias y funcionales (18 casos en pytest)
├── main.py                # Punto de entrada para iniciar el servicio del bot (CU06)
├── consultar_db.py        # Herramienta de administrador para inspeccionar SQLite (CU07, RF15)
├── proteger_env.py        # Utilidad criptográfica PBKDF2 + Fernet + DPAPI para proteger el .env
├── MATRIZ_DE_PRUEBAS.md   # Matriz formal de casos de prueba (esperado vs. observado)
├── .env.example           # Plantilla con token cifrado para el Grupo 1
└── requirements.txt       # Dependencias del proyecto
```

---

## Requisitos Previos

* **Python 3.11+**
* Conexión a Internet para comunicarse con la **Telegram Bot API** mediante *HTTPS Long Polling* (no requiere servidores públicos ni *webhooks*).

---

## Instalación y Ejecución Local (Windows / Linux)

### 1. Clonar el repositorio y crear el entorno virtual
```powershell
git clone https://github.com/The1Poi/Bot_Financiero.git
cd Bot_Financiero
python -m venv .venv
```

Activar el entorno virtual e instalar dependencias:
* **Windows (PowerShell):**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```
* **Linux / macOS (o PythonAnywhere):**
  ```bash
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

### 2. Desbloquear la configuración segura (`.env`)
Por seguridad (`RNF03`), el token del bot no se almacena en texto plano en el repositorio. Al ejecutar `--unlock` por primera vez, el sistema solicita la clave secreta del equipo, almacena la llave derivada de forma segura en el llavero del sistema (*Windows Credential Manager / DPAPI* o almacén privado `0600` en Linux) y genera automáticamente el archivo `.env` cifrado:

```bash
python proteger_env.py --unlock
```
* Para verificar que el cifrado y descifrado en memoria funcionan correctamente:
  ```bash
  python proteger_env.py --verify
  ```
* Para rotar el token en el futuro sin exponerlo en texto plano:
  ```bash
  python proteger_env.py --rotate
  ```

### 3. Iniciar el Chatbot (`CU06`)
```bash
python main.py
```
Al iniciar correctamente, el bot registrará el menú interactivo de comandos (`/gasto`, `/informacion`, `/cancelar`, `/start`) en Telegram y comenzará a escuchar mensajes.

### 4. Consultar los registros almacenados (`CU07` / `RF15`)
En otra terminal (con el entorno `.venv` activado), el administrador puede inspeccionar la base de datos local `gastos.db` y verificar que los montos se almacenan en **centavos (`INTEGER`)**:
```bash
python consultar_db.py
```

---

## Ejecución de Pruebas Automatizadas (Fase 4)

El proyecto incluye una suite de 18 pruebas que verifican todas las transiciones de la Tabla XI, la conversión monetaria de la Tabla XII, el aislamiento multiusuario y la prevención de falsas confirmaciones ante fallos de disco:

```bash
python -m pytest -v
```

---

## Autores

* **Carlos S. Antolinez**
* **Sebastián A. Basto**
* **Jeison S. Clavijo**
* **Johan C. Bonett**

*Programa de Ingeniería de Sistemas — Asignatura: Teoría de la Computación — Universidad de Pamplona (2026).*
