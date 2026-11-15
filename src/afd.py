"""
Módulo 2: Control de Estados — Autómata Finito Determinista (AFD)
(RF01, RF02, RF05, RF11, RF12, RNF01, Tabla XI).

Definición formal de la 5-tupla M = (Q, Σ, δ, q0, F):
  - Q  = {'S0', 'S1', 'S2'}
         S0: Inactivo (En reposo)
         S1: Esperando Monto
         S2: Esperando Concepto
  - Σ  = {'c', 'mv', 'mi', 'tv', 'ti', 'e'}
         c : Comando /gasto
         mv: Monto válido
         mi: Monto inválido
         tv: Concepto válido
         ti: Concepto inválido
         e : Mensaje fuera de secuencia
  - q0 = 'S0' (Estado inicial)
  - F  = {'S0'} (Estado de aceptación al finalizar el ciclo de registro)
"""
from dataclasses import dataclass

# Conjunto finito de estados Q
ESTADOS_Q: frozenset[str] = frozenset({"S0", "S1", "S2"})

# Alfabeto finito de entrada Σ
ALFABETO_SIGMA: frozenset[str] = frozenset({"c", "mv", "mi", "tv", "ti", "e"})

# Estado inicial q0 y conjunto de estados de aceptación F
ESTADO_INICIAL: str = "S0"
ESTADOS_ACEPTACION: frozenset[str] = frozenset({"S0"})

# Matriz de Transiciones δ: Q × Σ -> Q (Idéntica a la Tabla XI del documento IEEE)
MATRIZ_TRANSICIONES: dict[tuple[str, str], str] = {
    # Filas para símbolo 'c' (/gasto)
    ("S0", "c"): "S1",
    ("S1", "c"): "S1",
    ("S2", "c"): "S1",
    # Filas para símbolo 'mv' (Monto Válido)
    ("S0", "mv"): "S0",
    ("S1", "mv"): "S2",
    ("S2", "mv"): "S2",
    # Filas para símbolo 'mi' (Monto Inválido)
    ("S0", "mi"): "S0",
    ("S1", "mi"): "S1",  # RF04: conserva S1
    ("S2", "mi"): "S2",
    # Filas para símbolo 'tv' (Concepto Válido)
    ("S0", "tv"): "S0",
    ("S1", "tv"): "S1",
    ("S2", "tv"): "S0",  # Inicia I/O en SQLite y retorna a S0 (RF08-RF11)
    # Filas para símbolo 'ti' (Concepto Inválido)
    ("S0", "ti"): "S0",
    ("S1", "ti"): "S1",
    ("S2", "ti"): "S2",  # RF07: conserva S2
    # Filas para símbolo 'e' (Fuera de Secuencia)
    ("S0", "e"): "S0",
    ("S1", "e"): "S1",   # RF12: conserva S1 y datos temporales
    ("S2", "e"): "S2",   # RF12: conserva S2 y datos temporales
}


@dataclass
class SesionUsuarioAFD:
    """Estado independiente del AFD y datos temporales para cada usuario de Telegram."""
    id_usuario: int
    estado: str = ESTADO_INICIAL
    monto_centavos: int | None = None


class ControladorAFD:
    """
    Motor determinista que gestiona las transiciones δ(qk, σ) = qk+1
    aislando el estado por cada id_usuario de Telegram.
    """

    def __init__(self) -> None:
        self._sesiones: dict[int, SesionUsuarioAFD] = {}

    def obtener_sesion(self, id_usuario: int) -> SesionUsuarioAFD:
        """Retorna la sesión AFD del usuario o la inicializa en q0 = S0."""
        if id_usuario not in self._sesiones:
            self._sesiones[id_usuario] = SesionUsuarioAFD(id_usuario=id_usuario)
        return self._sesiones[id_usuario]

    def obtener_estado(self, id_usuario: int) -> str:
        """Devuelve el estado actual qk ∈ Q del usuario."""
        return self.obtener_sesion(id_usuario).estado

    @staticmethod
    def evaluar_transicion_pura(estado_actual: str, simbolo: str) -> str:
        """
        Función matemática de transición δ(qk, σ) -> qk+1 (RNF01).
        Garantiza una única transición determinista para cada par (estado, símbolo).
        """
        if estado_actual not in ESTADOS_Q:
            raise ValueError(f"Estado inválido fuera de Q: {estado_actual}")
        if simbolo not in ALFABETO_SIGMA:
            raise ValueError(f"Símbolo inválido fuera de Σ: {simbolo}")
        return MATRIZ_TRANSICIONES[(estado_actual, simbolo)]

    def aplicar_transicion(
        self,
        id_usuario: int,
        simbolo: str,
        monto_centavos: int | None = None,
    ) -> tuple[str, str]:
        """
        Aplica δ(qk, σ) a la sesión del usuario, preservando intactos los datos temporales
        ante entradas inválidas o fuera de secuencia (RF04, RF07, RF12).

        Retorna:
            (estado_anterior, estado_nuevo)
        """
        sesion = self.obtener_sesion(id_usuario)
        estado_anterior = sesion.estado
        estado_nuevo = self.evaluar_transicion_pura(estado_anterior, simbolo)

        # Si inicia o reinicia con /gasto ('c'), limpiar monto temporal previo
        if simbolo == "c":
            sesion.monto_centavos = None
        # Si transiciona de S1 a S2 con monto válido ('mv'), almacenar monto temporal
        elif estado_anterior == "S1" and simbolo == "mv" and monto_centavos is not None:
            sesion.monto_centavos = monto_centavos

        sesion.estado = estado_nuevo
        return estado_anterior, estado_nuevo

    def cancelar_flujo(self, id_usuario: int) -> None:
        """Reinicia manualmente la sesión del usuario al estado inactivo S0 (comando /cancelar)."""
        sesion = self.obtener_sesion(id_usuario)
        sesion.estado = ESTADO_INICIAL
        sesion.monto_centavos = None
