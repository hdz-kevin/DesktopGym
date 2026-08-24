"""Comprobaciones de la receta de empaquetado.

Un error aqui solo se notaria al instalar en la PC del gimnasio, cuando ya es
tarde; estas pruebas lo detectan en segundos.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "gym.spec"
INSTALLER = ROOT / "packaging" / "installer.iss"


@pytest.fixture(scope="module")
def spec_text() -> str:
    return SPEC.read_text(encoding="utf-8")


def test_existen_los_archivos_de_empaquetado():
    for path in (SPEC, INSTALLER, ROOT / "packaging" / "build.py"):
        assert path.exists(), f"Falta {path.name}"


def test_las_migraciones_viajan_en_el_ejecutable(spec_text):
    """Sin ellas la aplicacion no podria crear la base al instalarse."""
    assert '"migrations"' in spec_text
    assert "alembic.ini" in spec_text


def test_las_migraciones_existen_en_el_proyecto():
    versions = ROOT / "migrations" / "versions"
    assert (ROOT / "alembic.ini").exists()
    assert list(versions.glob("*.py")), "No hay ninguna migración generada"


def test_el_punto_de_entrada_existe():
    assert (ROOT / "gym" / "__main__.py").exists()


def test_se_compila_sin_consola(spec_text):
    assert "console=False" in spec_text


def test_el_instalador_conserva_los_datos_del_gimnasio():
    """Desinstalar no debe borrar la base ni los respaldos."""
    texto = INSTALLER.read_text(encoding="utf-8")
    assert "{localappdata}" in texto
    for peligroso in ("gym.sqlite", "backups", "photos"):
        assert f'Name: "{{localappdata}}\\{{#AppName}}\\{peligroso}' not in texto


def test_el_instalador_no_exige_administrador():
    texto = INSTALLER.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in texto


def test_el_instalador_ofrece_acceso_directo():
    texto = INSTALLER.read_text(encoding="utf-8")
    assert "desktopicon" in texto
    assert "{autodesktop}" in texto


def test_la_ruta_de_recursos_funciona_empaquetada(monkeypatch, tmp_path):
    """`resource_path` debe apuntar dentro del paquete cuando hay _MEIPASS."""
    import sys

    from gym.config import resource_path

    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resource_path("alembic.ini") == tmp_path / "alembic.ini"
