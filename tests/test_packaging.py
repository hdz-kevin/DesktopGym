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
    for path in (
        SPEC,
        INSTALLER,
        ROOT / "packaging" / "build.py",
        ROOT / "packaging" / "make_icon.py",
    ):
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


def test_el_ejecutable_incluye_la_camara(spec_text):
    """Sin QtMultimedia el .exe no puede encender la webcam de recepcion."""
    assert '"PySide6.QtMultimedia"' in spec_text
    assert '"PySide6.QtMultimediaWidgets"' in spec_text
    excludes_block = spec_text.split("excludes=[", 1)[1].split("]", 1)[0]
    assert "QtMultimedia" not in excludes_block


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


def test_el_instalador_usa_el_icono_generico():
    texto = INSTALLER.read_text(encoding="utf-8")
    assert "SetupIconFile=gym.ico" in texto
    assert (ROOT / "packaging" / "make_icon.py").exists()


def test_el_nombre_del_programa_no_es_el_del_gimnasio():
    """El .exe es DevGym; el kiosco y las paginas usan Settings.gym_name."""
    from gym.config import APP_NAME, Settings

    assert APP_NAME == "DevGym"
    assert Settings().gym_name == "Gimnasio"
    assert Settings().gym_name != APP_NAME


def test_la_identidad_del_programa_vive_en_un_solo_lugar(spec_text):
    """pyproject, el .exe e Inno Setup no deben volver a tener nombre o version propios."""
    import tomllib

    from gym import __version__

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["dynamic"] == ["version"]
    assert pyproject["tool"]["hatch"]["version"]["path"] == "gym/__init__.py"
    assert __version__, "Falta gym.__version__"
    assert "name=APP_NAME" in spec_text

    build = (ROOT / "packaging" / "build.py").read_text(encoding="utf-8")
    assert "/DAppName=" in build
    assert "/DAppVersion=" in build

    iss = INSTALLER.read_text(encoding="utf-8")
    assert "#ifndef AppName" in iss
    assert "#ifndef AppVersion" in iss
    assert "#define AppName" not in iss
    assert "#define AppVersion" not in iss


def test_los_datos_viven_bajo_el_nombre_del_programa(monkeypatch, tmp_path):
    import gym.config as config

    monkeypatch.delenv("GYM_DATA_DIR", raising=False)
    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert config.data_dir() == tmp_path / config.APP_NAME


def test_la_ruta_de_recursos_funciona_empaquetada(monkeypatch, tmp_path):
    """`resource_path` debe apuntar dentro del paquete cuando hay _MEIPASS."""
    import sys

    from gym.config import resource_path

    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resource_path("alembic.ini") == tmp_path / "alembic.ini"
