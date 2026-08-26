from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from gym.data.database import session_scope
from gym.data.models import Membership, Payment
from gym.domain.enums import MemberGender, MemberStatus
from gym.services import members as service
from gym.services.errors import NotFoundError, ServiceError, ValidationError


def alta(nombre: str = "Ana Lopez", **kwargs) -> int:
    form = service.MemberForm(
        name=nombre,
        gender=kwargs.pop("gender", MemberGender.FEMALE),
        birth_date=kwargs.pop("birth_date", None),
        photo_source=kwargs.pop("photo_source", None),
    )
    return service.create_member(form)


def dar_membresia(member_id: int, plan_id: int, category_id: int, dias_restantes: int) -> None:
    ahora = datetime.now()
    with session_scope() as session:
        membership = Membership(member_id=member_id, plan_category_id=category_id)
        session.add(membership)
        session.flush()
        session.add(
            Payment(
                membership_id=membership.id,
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

    def test_socio_nuevo_no_tiene_membresia(self, app_db):
        member = service.get_member(alta())
        assert member.status is MemberStatus.NO_MEMBERSHIP

    @pytest.mark.parametrize("nombre", ["", "  ", "Ab"])
    def test_rechaza_nombres_invalidos(self, app_db, nombre):
        with pytest.raises(ValidationError) as exc:
            alta(nombre)
        assert "name" in exc.value.errors

    def test_rechaza_fecha_de_nacimiento_futura(self, app_db):
        with pytest.raises(ValidationError) as exc:
            alta(birth_date=date.today() + timedelta(days=1))
        assert "birth_date" in exc.value.errors


class TestFoto:
    def _foto(self, tmp_path, nombre="foto.png", contenido=b"x"):
        path = tmp_path / nombre
        path.write_bytes(contenido)
        return path

    def test_guarda_la_foto_con_nombre_unico(self, app_db, tmp_path):
        origen = self._foto(tmp_path)
        member = service.get_member(alta(photo_source=origen))

        assert member.photo is not None
        assert member.photo != origen.name
        assert service.photo_path(member.photo).exists()

    def test_dos_socios_con_el_mismo_archivo_no_se_pisan(self, app_db, tmp_path):
        origen = self._foto(tmp_path)
        uno = service.get_member(alta("Socio Uno", photo_source=origen))
        dos = service.get_member(alta("Socio Dos", photo_source=origen))
        assert uno.photo != dos.photo

    def test_rechaza_formato_no_admitido(self, app_db, tmp_path):
        with pytest.raises(ValidationError) as exc:
            alta(photo_source=self._foto(tmp_path, "foto.gif"))
        assert "photo" in exc.value.errors

    def test_rechaza_foto_mayor_a_cinco_megas(self, app_db, tmp_path):
        pesada = self._foto(tmp_path, "grande.png", b"x" * (5 * 1024 * 1024 + 1))
        with pytest.raises(ValidationError) as exc:
            alta(photo_source=pesada)
        assert "photo" in exc.value.errors

    def test_cambiar_la_foto_borra_la_anterior(self, app_db, tmp_path):
        member_id = alta(photo_source=self._foto(tmp_path, "vieja.png"))
        anterior = service.get_member(member_id).photo

        service.update_member(
            member_id,
            service.MemberForm(
                name="Ana Lopez",
                gender=MemberGender.FEMALE,
                photo_source=self._foto(tmp_path, "nueva.png"),
            ),
        )

        assert service.photo_path(anterior) is None
        assert service.photo_path(service.get_member(member_id).photo) is not None

    def test_quitar_la_foto(self, app_db, tmp_path):
        member_id = alta(photo_source=self._foto(tmp_path))
        service.update_member(
            member_id,
            service.MemberForm(name="Ana Lopez", gender=MemberGender.FEMALE, remove_photo=True),
        )
        assert service.get_member(member_id).photo is None


class TestEditarYBorrar:
    def test_actualiza_los_datos(self, app_db):
        member_id = alta()
        service.update_member(
            member_id,
            service.MemberForm(
                name="Ana Maria Lopez",
                gender=MemberGender.FEMALE,
                birth_date=date(1995, 3, 20),
            ),
        )
        member = service.get_member(member_id)
        assert member.name == "Ana Maria Lopez"
        assert member.birth_date == date(1995, 3, 20)
        assert member.age is not None

    def test_editar_no_cambia_el_codigo(self, app_db):
        member_id = alta()
        original = service.get_member(member_id).code
        service.update_member(
            member_id, service.MemberForm(name="Otro Nombre", gender=MemberGender.MALE)
        )
        assert service.get_member(member_id).code == original

    def test_borra_socio_sin_historial(self, app_db):
        member_id = alta()
        service.delete_member(member_id)
        with pytest.raises(NotFoundError):
            service.get_member(member_id)

    def test_no_borra_socio_con_membresias(self, app_db, app_catalog):
        member_id = alta()
        dar_membresia(member_id, app_catalog["monthly_id"], app_catalog["category_id"], 10)

        with pytest.raises(ServiceError, match="historial"):
            service.delete_member(member_id)

    def test_editar_socio_inexistente(self, app_db):
        with pytest.raises(NotFoundError):
            service.update_member(
                999, service.MemberForm(name="Fantasma", gender=MemberGender.MALE)
            )


class TestListadoYFiltros:
    def _poblar(self, app_catalog):
        activo = alta("Activo Ramirez")
        vencido = alta("Vencido Torres")
        sin = alta("Nuevo Sanchez")
        dar_membresia(activo, app_catalog["monthly_id"], app_catalog["category_id"], 15)
        dar_membresia(vencido, app_catalog["monthly_id"], app_catalog["category_id"], -5)
        return activo, vencido, sin

    def test_lista_todo_por_defecto(self, app_db, app_catalog):
        self._poblar(app_catalog)
        rows, total = service.list_members()
        assert total == 3 and len(rows) == 3

    def test_ordena_por_nombre(self, app_db, app_catalog):
        self._poblar(app_catalog)
        rows, _ = service.list_members()
        assert [r.name for r in rows] == sorted(r.name for r in rows)

    @pytest.mark.parametrize(
        ("estado", "esperado"),
        [
            (MemberStatus.ACTIVE, "Activo Ramirez"),
            (MemberStatus.EXPIRED, "Vencido Torres"),
            (MemberStatus.NO_MEMBERSHIP, "Nuevo Sanchez"),
        ],
    )
    def test_filtra_por_estado(self, app_db, app_catalog, estado, esperado):
        self._poblar(app_catalog)
        rows, total = service.list_members(status=estado)
        assert total == 1
        assert rows[0].name == esperado
        assert rows[0].status is estado

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
        assert (stats.total, stats.active, stats.expired, stats.without_membership) == (3, 1, 1, 1)

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
