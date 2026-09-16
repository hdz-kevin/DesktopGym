"""Compila el ejecutable y, en Windows, el instalador.

Uso: uv run python packaging/build.py [--installer]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "gym.spec"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def project_version() -> str:
    """La version vive en gym/__init__.py; pyproject e Inno Setup la leen de ahi."""
    from gym import __version__

    return __version__


def run(command: list[str]) -> None:
    print(f"$ {' '.join(command)}")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def build_executable() -> Path:
    for folder in (DIST, BUILD):
        if folder.exists():
            shutil.rmtree(folder)

    print(f"Version {project_version()}")
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC)])

    name = "TecnoGym.exe" if sys.platform == "win32" else "TecnoGym"
    executable = DIST / name
    if not executable.exists():
        raise SystemExit(f"No se generó el ejecutable esperado en {executable}")

    size_mb = executable.stat().st_size / (1024 * 1024)
    print(f"Ejecutable listo: {executable} ({size_mb:.1f} MB)")
    return executable


def build_installer() -> None:
    if sys.platform != "win32":
        raise SystemExit("El instalador solo se puede compilar en Windows.")

    iscc = shutil.which("iscc")
    if iscc is None:
        raise SystemExit("No se encontró 'iscc'. Instala Inno Setup 6 y agrégalo al PATH.")

    version = project_version()
    run([iscc, f"/DAppVersion={version}", str(ROOT / "packaging" / "installer.iss")])
    print(f"Instalador listo en {DIST / 'installer'} (v{version})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compila TecnoGym")
    parser.add_argument("--installer", action="store_true", help="También compilar el instalador")
    args = parser.parse_args()

    build_executable()
    if args.installer:
        build_installer()


if __name__ == "__main__":
    main()
