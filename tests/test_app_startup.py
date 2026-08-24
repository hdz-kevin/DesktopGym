"""Prueba de arranque: la aplicacion completa se levanta y navega.

Las pruebas por modulo no detectarian un error al conectar las pantallas en
`build_window`, que es justo lo que rompe la aplicacion al abrirla.
"""

from __future__ import annotations

import pytest

from gym.__main__ import build_window
from gym.config import Settings
from gym.data.schema import seed_catalog
from gym.services import memberships as memberships_service
from gym.ui.main_window import NAV_ITEMS


@pytest.fixture
def app_window(qtbot, app_db):
    seed_catalog()
    window = build_window(Settings(gym_name="Gimnasio de Prueba"))
    qtbot.addWidget(window)
    return window


def test_arranca_con_todas_las_paginas(app_window):
    assert set(app_window.pages) == {item.key for item in NAV_ITEMS}


def test_abre_en_la_pantalla_de_bienvenida(app_window):
    assert app_window.stack.currentWidget() is app_window.pages["kiosk"]


def test_navega_por_todos_los_modulos(app_window):
    for item in NAV_ITEMS:
        app_window.show_page(item.key)
        assert app_window.stack.currentWidget() is app_window.pages[item.key]
        assert app_window.sidebar.buttons[item.key].isChecked()


def test_todas_las_paginas_se_actualizan_sin_error(app_window):
    for key in app_window.pages:
        app_window.pages[key].refresh()


def test_la_semilla_deja_precios_listos(app_db):
    """Al primer arranque debe poder venderse una membresía sin configurar nada."""
    seed_catalog()
    tipos = memberships_service.list_membership_types()
    duraciones = memberships_service.list_durations()

    assert len(tipos) >= 1
    assert len(duraciones) >= 1
    assert all(d.price_cents > 0 for d in duraciones)


def test_sembrar_dos_veces_no_duplica(app_db):
    seed_catalog()
    primera = len(memberships_service.list_membership_types())
    seed_catalog()

    assert len(memberships_service.list_membership_types()) == primera


def test_la_semilla_respeta_un_catalogo_existente(app_db):
    memberships_service.create_membership_type("Solo el mío")
    seed_catalog()

    tipos = [t.name for t in memberships_service.list_membership_types()]
    assert tipos == ["Solo el mío"]


def test_el_titulo_usa_el_nombre_del_gimnasio(app_window):
    assert "Gimnasio de Prueba" in app_window.windowTitle()
    assert app_window.sidebar.title.text() == "Gimnasio de Prueba"
