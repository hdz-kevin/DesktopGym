from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from gym.data.database import session_scope
from gym.data.models import Member, Payment
from gym.domain.enums import MemberStatus
from gym.services import members as service
from gym.services.errors import NotFoundError, ServiceError, ValidationError
from tests.conftest import default_category_id


def alta(nombre: str = "Ana Lopez", **kwargs) -> int:
    form = service.MemberForm(
        name=nombre,
        plan_category_id=kwargs.pop("plan_category_id", None) or default_category_id(),
        photo_jpeg=kwargs.pop("photo_jpeg", None),
    )
    return service.create_member(form)


def _form(nombre: str = "Ana Lopez", member_id: int | None = None, **kwargs) -> service.MemberForm:
    category_id = kwargs.pop("plan_category_id", None)
    if category_id is None and member_id is not None:
        category_id = service.get_member(member_id).plan_category_id
    return service.MemberForm(
        name=nombre,
        plan_category_id=category_id or default_category_id(),
        **kwargs,
    )


def dar_pago(member_id: int, plan_id: int, dias_restantes: int) -> None:
    ahora = datetime.now()
    with session_scope() as session:
        session.add(
            Payment(
                member_id=member_id,
                plan_id=plan_id,
                start_date=ahora - timedelta(days=30),
                end_date=ahora + timedelta(days=dias_restantes),
                price_paid_cents=40000,
            )
        )


class TestCrear:
    def test_asigna_codigo_de_cinco_digitos(self, app_db):
        member_id = alta()
        member = service.get_member(member_id)
        assert len(member.code) == 5 and member.code.isdigit()

    def test_los_codigos_no_se_repiten(self, app_db):
        codigos = {service.get_member(alta(f"Socio {i}")).code for i in range(25)}
        assert len(codigos) == 25

    def test_recorta_espacios_del_nombre(self, app_db):
        member = service.get_member(alta("  Ana Lopez  "))
        assert member.name == "Ana Lopez"

    def test_socio_nuevo_esta_vencido(self, app_db):
        member = service.get_member(alta())
        assert member.status is MemberStatus.EXPIRED

    @pytest.mark.parametrize("nombre", ["", "  ", "Ab"])
    def test_rechaza_nombres_invalidos(self, app_db, nombre):
        with pytest.raises(ValidationError) as exc:
            alta(nombre)
        assert "name" in exc.value.errors


class TestFoto:
    def _jpeg(self, contenido: bytes | None = None) -> bytes:
        if contenido is not None:
            return contenido
        from PySide6.QtCore import QBuffer, QIODevice
        from PySide6.QtGui import QColor, QImage

        image = QImage(1, 1, QImage.Format.Format_RGB32)
        image.fill(QColor(200, 80, 80))
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        assert image.save(buffer, "JPEG", 85)
        return bytes(buffer.data())

    def test_guarda_la_foto_con_nombre_unico(self, app_db):
        member = service.get_member(alta(photo_jpeg=self._jpeg()))

        assert member.photo is not None
        assert member.photo.endswith(".jpg")
        assert service.photo_path(member.photo).exists()

    def test_dos_socios_con_el_mismo_archivo_no_se_pisan(self, app_db):
        jpeg = self._jpeg()
        uno = service.get_member(alta("Socio Uno", photo_jpeg=jpeg))
        dos = service.get_member(alta("Socio Dos", photo_jpeg=jpeg))
        assert uno.photo != dos.photo

    def test_rechaza_bytes_vacios(self, app_db):
        with pytest.raises(ValidationError) as exc:
            alta(photo_jpeg=b"")
        assert "photo" in exc.value.errors

    def test_rechaza_formato_no_jpeg(self, app_db):
        with pytest.raises(ValidationError) as exc:
            alta(photo_jpeg=b"GIF89a")
        assert "photo" in exc.value.errors

    def test_rechaza_foto_mayor_a_cinco_megas(self, app_db):
        pesada = b"\xff\xd8" + b"x" * (5 * 1024 * 1024)
        with pytest.raises(ValidationError) as exc:
            alta(photo_jpeg=pesada)
        assert "photo" in exc.value.errors

    def test_cambiar_la_foto_borra_la_anterior(self, app_db):
        member_id = alta(photo_jpeg=self._jpeg())
        anterior = service.get_member(member_id).photo

        service.update_member(
            member_id,
            _form("Ana Lopez", member_id=member_id, photo_jpeg=self._jpeg()),
        )

        assert service.photo_path(anterior) is None
        assert service.photo_path(service.get_member(member_id).photo) is not None

    def test_quitar_la_foto(self, app_db):
        member_id = alta(photo_jpeg=self._jpeg())
        service.update_member(
            member_id,
            _form("Ana Lopez", member_id=member_id, remove_photo=True),
        )
        assert service.get_member(member_id).photo is None


class TestEditarYBorrar:
    def test_actualiza_los_datos(self, app_db):
        member_id = alta()
        service.update_member(
            member_id,
            _form("Ana Maria Lopez", member_id=member_id),
        )
        member = service.get_member(member_id)
        assert member.name == "Ana Maria Lopez"

    def test_editar_no_cambia_el_codigo(self, app_db):
        member_id = alta()
        original = service.get_member(member_id).code
        service.update_member(member_id, _form("Otro Nombre", member_id=member_id))
        assert service.get_member(member_id).code == original

    def test_borra_socio_sin_historial(self, app_db):
        member_id = alta()
        service.delete_member(member_id)
        with pytest.raises(NotFoundError):
            service.get_member(member_id)

    def test_no_borra_socio_con_pagos(self, app_db, app_catalog):
        member_id = alta()
        dar_pago(member_id, app_catalog["monthly_id"], 10)

        with pytest.raises(ServiceError, match="pagos registrados"):
            service.delete_member(member_id)

    def test_editar_socio_inexistente(self, app_db):
        with pytest.raises(NotFoundError):
            service.update_member(999, _form("Fantasma"))


class TestListadoYFiltros:
    def _poblar(self, app_catalog):
        activo = alta("Activo Ramirez")
        vencido = alta("Vencido Torres")
        sin = alta("Nuevo Sanchez")
        dar_pago(activo, app_catalog["monthly_id"], 15)
        dar_pago(vencido, app_catalog["monthly_id"], -5)
        return activo, vencido, sin

    def test_lista_todo_por_defecto(self, app_db, app_catalog):
        self._poblar(app_catalog)
        rows, total = service.list_members()
        assert total == 3 and len(rows) == 3

    def test_ordena_del_mas_reciente_al_mas_viejo(self, app_db):
        viejo = alta("Primero")
        nuevo = alta("Segundo")
        rows, _ = service.list_members()
        assert [r.id for r in rows] == [nuevo, viejo]

    def test_desempata_por_id_si_la_fecha_coincide(self, app_db):
        primero = alta("Primero")
        segundo = alta("Segundo")
        mismo_instante = datetime(2026, 1, 15, 10, 0, 0)
        with session_scope() as session:
            for member_id in (primero, segundo):
                session.get(Member, member_id).created_at = mismo_instante

        rows, _ = service.list_members()
        assert [r.id for r in rows] == [segundo, primero]

    def test_filtra_activos(self, app_db, app_catalog):
        self._poblar(app_catalog)
        rows, total = service.list_members(status=MemberStatus.ACTIVE)
        assert total == 1
        assert rows[0].name == "Activo Ramirez"
        assert rows[0].status is MemberStatus.ACTIVE

    def test_filtra_vencidos(self, app_db, app_catalog):
        self._poblar(app_catalog)
        rows, total = service.list_members(status=MemberStatus.EXPIRED)
        assert total == 2
        assert {row.name for row in rows} == {"Vencido Torres", "Nuevo Sanchez"}
        assert all(row.status is MemberStatus.EXPIRED for row in rows)

    def test_busca_por_nombre_sin_importar_mayusculas(self, app_db, app_catalog):
        self._poblar(app_catalog)
        rows, total = service.list_members(search="ramirez")
        assert total == 1 and rows[0].name == "Activo Ramirez"

    def test_busca_por_codigo(self, app_db, app_catalog):
        activo, _, _ = self._poblar(app_catalog)
        codigo = service.get_member(activo).code
        rows, total = service.list_members(search=codigo)
        assert total == 1 and rows[0].id == activo

    def test_pagina_los_resultados(self, app_db):
        for i in range(7):
            alta(f"Socio {i:02d}")
        primera, total = service.list_members(offset=0, limit=5)
        segunda, _ = service.list_members(offset=5, limit=5)

        assert total == 7
        assert len(primera) == 5 and len(segunda) == 2
        assert {m.id for m in primera}.isdisjoint({m.id for m in segunda})

    def test_estadisticas(self, app_db, app_catalog):
        self._poblar(app_catalog)
        stats = service.member_stats()
        assert (stats.total, stats.active, stats.expired) == (3, 1, 2)

    def test_estadisticas_sin_socios(self, app_db):
        stats = service.member_stats()
        assert stats.total == 0


class TestBusquedaPorCodigo:
    def test_encuentra_socio(self, app_db):
        member_id = alta()
        codigo = service.get_member(member_id).code
        assert service.find_by_code(codigo).id == member_id

    def test_ignora_espacios(self, app_db):
        codigo = service.get_member(alta()).code
        assert service.find_by_code(f"  {codigo}  ") is not None

    def test_codigo_inexistente(self, app_db):
        assert service.find_by_code("00000") is None
