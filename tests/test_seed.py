"""Datos de prueba: llenar la base y volver al catalogo inicial."""

from __future__ import annotations

from io import StringIO

from gym.config import Settings, backups_dir, photos_dir
from gym.data.schema import SEED_CATALOG, seed_catalog
from gym.seed import main as seed_cli
from gym.services import members as members_service
from gym.services import memberships as memberships_service
from gym.services import products as products_service
from gym.services import sales as sales_service
from gym.services.seeder import reset_to_catalog, seed
from gym.services.visits import VisitRange
from gym.services.visits import totals as visit_totals
from gym.single_instance import InstanceLock


def _tipos() -> list[str]:
    return [t.name for t in memberships_service.list_plan_categories()]


def _planes() -> list[tuple[str, str, int]]:
    return [(d.plan_category.name, d.name, d.price_cents) for d in memberships_service.list_plans()]


class TestReset:
    def test_en_base_vacia_deja_el_catalogo_inicial(self, app_db):
        reset_to_catalog()

        assert _tipos() == sorted(SEED_CATALOG)
        assert members_service.member_stats().total == 0
        assert memberships_service.membership_stats().total == 0
        _, productos = products_service.list_products()
        assert productos == 0
        assert visit_totals(VisitRange.ALL).count == 0
        assert sales_service.totals(VisitRange.ALL).count == 0

    def test_borra_socios_visitas_productos_y_ventas(self, app_db):
        seed()
        reset_to_catalog()

        stats = members_service.member_stats()
        assert stats.total == 0
        assert memberships_service.membership_stats().total == 0
        _, productos = products_service.list_products()
        assert productos == 0
        assert visit_totals(VisitRange.ALL).count == 0
        assert sales_service.totals(VisitRange.ALL).count == 0

    def test_restaura_precios_aunque_el_catalogo_se_haya_editado(self, app_db):
        seed_catalog()
        memberships_service.create_plan_category("VIP")

        reset_to_catalog()

        assert _tipos() == ["Estudiante", "General"]
        esperadas = {
            (tipo, nombre, precio)
            for tipo, filas in SEED_CATALOG.items()
            for nombre, _amount, _unit, precio in filas
        }
        assert set(_planes()) == esperadas

    def test_borra_fotos_sueltas_y_no_toca_respaldos_ni_ajustes(self, app_db):
        foto = photos_dir() / "demo.jpg"
        foto.write_bytes(b"jpg")
        respaldo = backups_dir() / "gym-20260101-120000.sqlite"
        respaldo.write_bytes(b"sqlite")
        settings = Settings(gym_name="Gimnasio Demo")
        settings.save()

        reset_to_catalog()

        assert not foto.exists()
        assert respaldo.exists()
        assert Settings.load().gym_name == "Gimnasio Demo"


class TestSeed:
    def test_llena_todas_las_pantallas(self, app_db):
        summary = seed()

        stats = members_service.member_stats()
        memberships = memberships_service.membership_stats()
        _, productos = products_service.list_products()

        assert summary.members == stats.total == 32
        assert summary.memberships == memberships.total
        assert summary.visits == visit_totals(VisitRange.ALL).count
        assert summary.products == productos == 11
        assert summary.sales == sales_service.totals(VisitRange.ALL).count == 18

        assert stats.active > 0
        assert stats.expired > 0
        assert stats.without_membership > 0
        assert memberships.active > 0
        assert memberships.expired > 0
        assert visit_totals(VisitRange.TODAY).count > 0
        assert sales_service.totals(VisitRange.TODAY).count > 0
        assert products_service.low_stock()
        assert any(not p.is_active for p in products_service.list_products()[0])
        assert any(p.stock == 0 for p in products_service.list_products()[0])

    def test_cabe_en_mas_de_una_pagina_de_socios(self, app_db):
        seed()
        assert members_service.member_stats().total > 25

    def test_es_idempotente(self, app_db):
        primero = seed()
        segundo = seed()
        assert primero == segundo
        assert members_service.member_stats().total == primero.members

    def test_conserva_el_catalogo_inicial(self, app_db):
        seed()
        assert _tipos() == ["Estudiante", "General"]


class TestCli:
    def test_seed_con_yes_escribe_en_la_base_del_fixture(self, app_db, monkeypatch, capsys):
        monkeypatch.setattr("gym.seed.prepare_database", lambda: None)

        assert seed_cli(["seed", "--yes"]) == 0

        captured = capsys.readouterr()
        assert "32 socios" in captured.out
        assert members_service.member_stats().total == 32

    def test_reset_con_yes_deja_solo_el_catalogo(self, app_db, monkeypatch):
        monkeypatch.setattr("gym.seed.prepare_database", lambda: None)
        seed()

        assert seed_cli(["reset", "--yes"]) == 0
        assert members_service.member_stats().total == 0
        assert _tipos() == ["Estudiante", "General"]

    def test_sin_confirmacion_no_toca_nada(self, app_db, monkeypatch):
        monkeypatch.setattr("gym.seed.prepare_database", lambda: None)
        monkeypatch.setattr("sys.stdin", StringIO("no\n"))
        seed_catalog()

        assert seed_cli(["seed"]) == 1
        assert members_service.member_stats().total == 0

    def test_rehusa_si_la_aplicacion_esta_abierta(self, app_db, monkeypatch):
        monkeypatch.setattr("gym.seed.prepare_database", lambda: None)
        lock = InstanceLock()
        assert lock.acquire()
        try:
            assert seed_cli(["reset", "--yes"]) == 1
        finally:
            lock.release()
        assert members_service.member_stats().total == 0
