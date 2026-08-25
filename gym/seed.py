"""Herramienta de desarrollo para llenar o vaciar la base del usuario.

Por defecto escribe en la SQLite real de TecnoGym (en macOS,
~/Library/Application Support/TecnoGym/gym.sqlite). Cierra la aplicacion
antes: dos procesos no pueden pelearse el mismo archivo.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gym.config import database_path
from gym.data.database import dispose_engine, init_engine
from gym.data.schema import prepare_database
from gym.services.seeder import reset_to_catalog, seed
from gym.single_instance import InstanceLock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Llena o vacia la base de datos de TecnoGym. "
            "Por defecto usa la del usuario, no una carpeta de demostracion."
        )
    )
    parser.add_argument(
        "command",
        choices=("seed", "reset"),
        help="seed: datos de prueba. reset: solo el catalogo inicial de precios.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="No pedir confirmacion.",
    )
    args = parser.parse_args(argv)

    dispose_engine()
    init_engine()

    lock = InstanceLock()
    if not lock.acquire():
        print(
            "El sistema está abierto. Cierra TecnoGym antes de cambiar los datos de prueba.",
            file=sys.stderr,
        )
        return 1

    try:
        prepare_database()
        path = database_path()
        if not args.yes and not _confirm(path, args.command):
            print("Cancelado.")
            return 1

        if args.command == "reset":
            reset_to_catalog()
            print(f"Listo. Solo queda el catálogo inicial de precios en:\n  {path}")
            return 0

        summary = seed()
        print(
            "Listo. Datos de prueba en:\n"
            f"  {path}\n\n"
            f"  {summary.members} socios\n"
            f"  {summary.memberships} membresías\n"
            f"  {summary.visits} visitas\n"
            f"  {summary.products} productos\n"
            f"  {summary.sales} ventas"
        )
        return 0
    finally:
        lock.release()


def _confirm(path: Path, command: str) -> bool:
    if command == "seed":
        action = "Se vaciará y se llenará con socios, visitas, productos y ventas de prueba."
    else:
        action = "Se vaciará y quedará solo el catálogo inicial (General y Estudiante)."
    print(
        f"{action}\n\n"
        f"  {path}\n\n"
        "Los respaldos y los ajustes del gimnasio no se tocan.\n"
        "Escribe si para continuar: ",
        end="",
        flush=True,
    )
    try:
        answer = input().strip().casefold()
    except EOFError:
        return False
    return answer in {"si", "sí", "s", "yes", "y"}


if __name__ == "__main__":
    raise SystemExit(main())
