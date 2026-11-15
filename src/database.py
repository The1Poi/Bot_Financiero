"""
Módulo 4: Persistencia de Datos en SQLite (RF08, RF09, RF10, RF15, RNF02, RNF05, Fig. 4).
Implementa el esquema relacional USUARIO (1) -> (N) GASTO con consultas SQL 100%
parametrizadas (?) y almacenamiento de montos en centavos (INTEGER).
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from src.config import SQLITE_DB_PATH


class BaseDatosGastos:
    """Gestor de persistencia local en SQLite para el Chatbot Financiero."""

    def __init__(self, db_path: str | Path = SQLITE_DB_PATH) -> None:
        self.db_path = str(db_path)
        self.inicializar_esquema()

    def _conectar(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def inicializar_esquema(self) -> None:
        """Crea las tablas normalizadas USUARIO y GASTO si no existen (Fig. 4 del documento IEEE)."""
        sql_usuario = """
        CREATE TABLE IF NOT EXISTS USUARIO (
            id_usuario INTEGER PRIMARY KEY,
            username_telegram TEXT NULL,
            fecha_registro TEXT NOT NULL
        );
        """
        sql_gasto = """
        CREATE TABLE IF NOT EXISTS GASTO (
            id_gasto INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario INTEGER NOT NULL,
            monto INTEGER NOT NULL,
            concepto TEXT NOT NULL,
            fecha_hora TEXT NOT NULL,
            FOREIGN KEY (id_usuario) REFERENCES USUARIO(id_usuario)
        );
        """
        with self._conectar() as conn:
            conn.execute(sql_usuario)
            conn.execute(sql_gasto)
            conn.commit()

    def registrar_gasto(
        self,
        id_usuario: int,
        username_telegram: str | None,
        monto_centavos: int,
        concepto: str,
    ) -> tuple[bool, str, str | None]:
        """
        Almacena o actualiza el usuario y registra el gasto validado en SQLite (RF08, RF09, RF10, RNF02).
        Usa consultas estrictamente parametrizadas (?) para impedir inyección SQL.

        Retorna:
            (exito, fecha_hora_iso, mensaje_error)
        """
        marca_temporal = datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            with self._conectar() as conn:
                cursor = conn.cursor()
                # 1. Asegurar registro del usuario en la tabla USUARIO (parámetros '?')
                cursor.execute(
                    """
                    INSERT INTO USUARIO (id_usuario, username_telegram, fecha_registro)
                    VALUES (?, ?, ?)
                    ON CONFLICT(id_usuario) DO UPDATE SET username_telegram = excluded.username_telegram;
                    """,
                    (id_usuario, username_telegram, marca_temporal),
                )

                # 2. Insertar el gasto validado en centavos (INTEGER) en la tabla GASTO
                cursor.execute(
                    """
                    INSERT INTO GASTO (id_usuario, monto, concepto, fecha_hora)
                    VALUES (?, ?, ?, ?);
                    """,
                    (id_usuario, int(monto_centavos), concepto, marca_temporal),
                )
                conn.commit()
            return True, marca_temporal, None
        except sqlite3.Error as exc:
            return False, marca_temporal, str(exc)

    def obtener_gastos_usuario(self, id_usuario: int, limite: int = 5) -> dict:
        """
        Consulta únicamente los gastos pertenecientes al id_usuario indicado (aislamiento multiusuario).
        Retorna el conteo total, la suma en centavos y los últimos registros.
        """
        with self._conectar() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) AS total_registros, COALESCE(SUM(monto), 0) AS suma_centavos
                FROM GASTO
                WHERE id_usuario = ?;
                """,
                (id_usuario,),
            )
            resumen = cursor.fetchone()

            cursor.execute(
                """
                SELECT id_gasto, monto, concepto, fecha_hora
                FROM GASTO
                WHERE id_usuario = ?
                ORDER BY id_gasto DESC
                LIMIT ?;
                """,
                (id_usuario, limite),
            )
            ultimos = [dict(row) for row in cursor.fetchall()]

        return {
            "total_registros": int(resumen["total_registros"]) if resumen else 0,
            "suma_centavos": int(resumen["suma_centavos"]) if resumen else 0,
            "ultimos_gastos": ultimos,
        }

    def listar_todos_los_registros(self) -> tuple[list[dict], list[dict]]:
        """Utilidad para el Administrador del prototipo (CU07, RF15)."""
        with self._conectar() as conn:
            usuarios = [
                dict(r)
                for r in conn.execute(
                    "SELECT id_usuario, username_telegram, fecha_registro FROM USUARIO ORDER BY fecha_registro DESC;"
                ).fetchall()
            ]
            gastos = [
                dict(r)
                for r in conn.execute(
                    "SELECT id_gasto, id_usuario, monto, concepto, fecha_hora FROM GASTO ORDER BY id_gasto DESC;"
                ).fetchall()
            ]
        return usuarios, gastos
