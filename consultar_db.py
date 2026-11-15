"""
Script del Administrador del Prototipo (CU07, RF15).
Permite consultar en consola los usuarios y gastos almacenados en el archivo SQLite local,
verificando que los montos se guardan como enteros en centavos (INTEGER - Tabla XII).
"""
from src.database import BaseDatosGastos
from src.validador import formatear_centavos_a_moneda


def mostrar_registros_consola() -> None:
    db = BaseDatosGastos()
    usuarios, gastos = db.listar_todos_los_registros()

    print("=" * 78)
    print(f"CONSULTA DE BASE DE DATOS LOCAL SQLite ({db.db_path}) — CU07 / RF15")
    print("=" * 78)

    print(f"\n[TABLA USUARIO] ({len(usuarios)} registrados):")
    if not usuarios:
        print("  (Sin usuarios registrados aún)")
    else:
        for u in usuarios:
            print(
                f"  • id_usuario={u['id_usuario']} | username=@{u['username_telegram']} | registro={u['fecha_registro']}"
            )

    print(f"\n[TABLA GASTO] ({len(gastos)} registrados):")
    if not gastos:
        print("  (Sin gastos registrados aún)")
    else:
        for g in gastos:
            moneda = formatear_centavos_a_moneda(g["monto"])
            print(
                f"  • #{g['id_gasto']} | id_usuario={g['id_usuario']} | "
                f"monto_sqlite={g['monto']} centavos ({moneda}) | "
                f"concepto='{g['concepto']}' | fecha='{g['fecha_hora']}'"
            )
    print("=" * 78)


if __name__ == "__main__":
    mostrar_registros_consola()
