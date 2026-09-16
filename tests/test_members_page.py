"""Pruebas de las pantallas de socios y kiosco."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import Qt

from gym.config import Settings
from gym.data.database import session_scope
from gym.data.models import Membership, Payment
from gym.domain.enums import MemberGender, MemberStatus
from gym.services import members as service
from gym.ui.dialogs.camera_capture import (
    CameraCaptureDialog,
    choose_camera,
    encode_jpeg,
    is_virtual_camera,
)
from gym.ui.dialogs.member_form import MemberFormDialog
from gym.ui.dialogs.member_profile import MemberProfileDialog
from gym.ui.main_window import MainWindow
from gym.ui.pages.kiosk import PHOTO_SIZE, RESULT_HOLD_MS, KioskPage, _clock_parts
from gym.ui.pages.members import MembersPage
from gym.ui.theme import DANGER, SUCCESS, TEXT
from gym.ui.widgets.feedback import Toast


@pytest.fixture
def window(qtbot, app_db):
    window = MainWindow(Settings(gym_name="Gimnasio de Prueba"))
    qtbot.addWidget(window)
    return window


def alta(nombre="Ana Lopez", gender=MemberGender.FEMALE) -> int:
    return service.create_member(service.MemberForm(name=nombre, gender=gender))


def dar_periodo(member_id: int, catalog: dict, dias: int) -> None:
    ahora = datetime.now()
    with session_scope() as session:
        membership = Membership(member_id=member_id, plan_category_id=catalog["category_id"])
        session.add(membership)
        session.flush()
        session.add(
            Payment(
                membership_id=membership.id,
                plan_id=catalog["monthly_id"],
                start_date=ahora - timedelta(days=30),
                end_date=ahora + timedelta(days=dias),
                price_paid_cents=40000,
            )
        )


class TestMembersPage:
    def test_muestra_los_socios(self, qtbot, window):
        alta("Ana Lopez")
        alta("Beto Ruiz")

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.table.model.rowCount() == 2

    def test_estadisticas_reflejan_los_estados(self, qtbot, window, app_catalog):
        activo = alta("Activo")
        alta("Sin membresia")
        dar_periodo(activo, app_catalog, dias=10)

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.stat_total.value_label.text() == "2"
        assert page.stat_active.value_label.text() == "1"
        assert page.stat_none.value_label.text() == "1"

    def test_filtrar_por_activos(self, qtbot, window, app_catalog):
        activo = alta("Activo Ramirez")
        alta("Nuevo Sanchez")
        dar_periodo(activo, app_catalog, dias=10)

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page._on_filter(MemberStatus.ACTIVE)

        assert page.table.model.rowCount() == 1
        assert page.table.model.record_at(0).name == "Activo Ramirez"

    def test_buscar_por_nombre(self, qtbot, window):
        alta("Ana Lopez")
        alta("Beto Ruiz")

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page._on_search("beto")

        assert page.table.model.rowCount() == 1
        assert page.table.model.record_at(0).name == "Beto Ruiz"

    def test_buscar_vuelve_a_la_primera_pagina(self, qtbot, window):
        for i in range(30):
            alta(f"Socio {i:02d}")

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page.table.go_to_page(2)
        assert page.table.page == 2

        page._on_search("Socio 0")
        assert page.table.page == 1

    def test_sin_seleccion_avisa_en_vez_de_fallar(self, qtbot, window):
        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()

        page.edit_selected()
        page.delete_selected()

    def test_estado_vacio(self, qtbot, window):
        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.table.model.rowCount() == 0
        assert page.table.summary.text() == "Sin resultados"


class TestMemberFormDialog:
    def test_guarda_un_socio_nuevo(self, qtbot, window):
        dialog = MemberFormDialog(window)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Carlos Mendez")
        dialog.accept()

        assert dialog.member_id is not None
        assert service.get_member(dialog.member_id).name == "Carlos Mendez"

    def test_muestra_error_en_el_campo_invalido(self, qtbot, window):
        dialog = MemberFormDialog(window)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Ab")
        dialog.accept()

        assert dialog.result() == 0
        assert dialog.name_field.error.isVisibleTo(dialog)
        assert "3 caracteres" in dialog.name_field.error.text()

    def test_precarga_los_datos_al_editar(self, qtbot, window):
        member_id = alta("Ana Lopez")
        member = service.get_member(member_id)

        dialog = MemberFormDialog(window, member)
        qtbot.addWidget(dialog)

        assert dialog.name_input.text() == "Ana Lopez"
        assert dialog.build_form().gender is MemberGender.FEMALE

    def test_editar_conserva_el_codigo(self, qtbot, window):
        member_id = alta("Ana Lopez")
        codigo = service.get_member(member_id).code

        dialog = MemberFormDialog(window, service.get_member(member_id))
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Ana Maria Lopez")
        dialog.accept()

        actualizado = service.get_member(member_id)
        assert actualizado.name == "Ana Maria Lopez"
        assert actualizado.code == codigo

    def test_el_boton_es_tomar_foto(self, qtbot, window):
        dialog = MemberFormDialog(window)
        qtbot.addWidget(dialog)
        assert dialog.take_photo.text() == "Tomar foto"

    def test_sin_camara_avisa_y_permite_guardar(self, qtbot, window, monkeypatch):
        monkeypatch.setattr("gym.ui.dialogs.member_form.camera_device", lambda: None)
        dialog = MemberFormDialog(window)
        qtbot.addWidget(dialog)
        dialog.show()
        dialog.name_input.setText("Carlos Mendez")
        dialog.take_photo.click()

        toasts = dialog.findChildren(Toast)
        assert toasts
        assert "cámara" in toasts[0].text()
        assert dialog.build_form().photo_jpeg is None

        dialog.accept()
        assert dialog.member_id is not None

    def test_build_form_manda_el_jpeg(self, qtbot, window):
        from PySide6.QtGui import QColor, QImage

        image = QImage(8, 8, QImage.Format.Format_RGB32)
        image.fill(QColor(200, 80, 80))
        jpeg = encode_jpeg(image)

        dialog = MemberFormDialog(window)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Carlos Mendez")
        dialog._photo_jpeg = jpeg

        assert dialog.build_form().photo_jpeg == jpeg


class TestCameraCaptureDialog:
    def _image(self):
        from PySide6.QtGui import QColor, QImage

        image = QImage(20, 20, QImage.Format.Format_RGB32)
        image.fill(QColor(200, 80, 80))
        return image

    def test_capturar_muestra_el_still_y_retomar_vuelve_al_visor(self, qtbot, window):
        dialog = CameraCaptureDialog(window, start_camera=False)
        qtbot.addWidget(dialog)
        dialog.show()

        assert dialog.viewfinder.isVisibleTo(dialog)
        assert not dialog.still.isVisibleTo(dialog)
        assert dialog.capture_button.isVisibleTo(dialog)
        assert not dialog.use_button.isVisibleTo(dialog)

        dialog._show_preview(self._image())

        assert not dialog.viewfinder.isVisibleTo(dialog)
        assert dialog.still.isVisibleTo(dialog)
        assert dialog.use_button.isVisibleTo(dialog)
        assert dialog.retake_button.isVisibleTo(dialog)
        assert not dialog.capture_button.isVisibleTo(dialog)

        dialog._retake()

        assert dialog.viewfinder.isVisibleTo(dialog)
        assert not dialog.still.isVisibleTo(dialog)
        assert dialog.capture_button.isVisibleTo(dialog)
        assert not dialog.use_button.isVisibleTo(dialog)

    def test_usar_esta_foto_devuelve_jpeg(self, qtbot, window):
        dialog = CameraCaptureDialog(window, start_camera=False)
        qtbot.addWidget(dialog)
        dialog._show_preview(self._image())
        dialog._use_photo()

        assert dialog.jpeg is not None
        assert dialog.jpeg.startswith(b"\xff\xd8")
        assert dialog.result() == dialog.DialogCode.Accepted


class TestCamaraVirtual:
    def test_obs_es_virtual(self):
        assert is_virtual_camera("OBS Virtual Camera")
        assert is_virtual_camera("OBS-Camera")

    def test_facetime_es_fisica(self):
        assert not is_virtual_camera("FaceTime HD Camera")
        assert not is_virtual_camera("Integrated Webcam")

    def test_otras_virtuales(self):
        assert is_virtual_camera("Camo Camera")
        assert is_virtual_camera("Snap Camera")
        assert is_virtual_camera("ManyCam")
        assert is_virtual_camera("Continuity Camera")

    def test_si_el_default_es_obs_usa_la_webcam(self):
        elegido = choose_camera(
            ["OBS Virtual Camera", "FaceTime HD Camera"],
            "OBS Virtual Camera",
        )
        assert elegido == "FaceTime HD Camera"

    def test_si_el_default_es_fisica_la_respeta(self):
        elegido = choose_camera(
            ["USB Camera", "FaceTime HD Camera"],
            "FaceTime HD Camera",
        )
        assert elegido == "FaceTime HD Camera"

    def test_sin_camaras(self):
        assert choose_camera([], None) is None


class TestMemberProfileDialog:
    def test_abre_para_socio_sin_membresia(self, qtbot, window):
        member = service.get_member(alta())
        dialog = MemberProfileDialog(member, window)
        qtbot.addWidget(dialog)

    def test_abre_para_socio_con_membresia(self, qtbot, window, app_catalog):
        member_id = alta()
        dar_periodo(member_id, app_catalog, dias=10)
        dialog = MemberProfileDialog(service.get_member(member_id), window)
        qtbot.addWidget(dialog)


class TestKioskPage:
    def _page(self, qtbot, window):
        page = KioskPage(window)
        qtbot.addWidget(page)
        page.refresh()
        return page

    def _assert_idle(self, page: KioskPage) -> None:
        assert not page.photo_slot.isVisibleTo(page)
        assert not page.result_name.isVisibleTo(page)
        assert not page.result_code_row.isVisibleTo(page)
        assert not page.result_detail.isVisibleTo(page)
        assert page.result_block.isVisibleTo(page)
        assert page.result_block.minimumHeight() == PHOTO_SIZE
        assert page.result_block.maximumHeight() == PHOTO_SIZE

    def test_codigo_valido_da_bienvenida(self, qtbot, window, app_catalog):
        member_id = alta("Ana Lopez")
        dar_periodo(member_id, app_catalog, dias=10)
        codigo = service.get_member(member_id).code

        page = self._page(qtbot, window)
        page.code_input.setText(codigo)

        assert page.result_name.text() == "Ana Lopez"
        assert page.result_name.isVisibleTo(page)
        assert page.photo_slot.isVisibleTo(page)
        assert page.photo_slot.pixmap() is not None
        assert not page.photo_slot.pixmap().isNull()
        assert SUCCESS in page.result_name.styleSheet()

    def test_membresia_vencida_niega_el_paso(self, qtbot, window, app_catalog):
        member_id = alta("Vencido Torres")
        dar_periodo(member_id, app_catalog, dias=-5)
        codigo = service.get_member(member_id).code

        page = self._page(qtbot, window)
        page.code_input.setText(codigo)

        assert page.result_name.text() == "Vencido Torres"
        assert page.result_name.isVisibleTo(page)
        assert page.result_code_label.text() == "Código:"
        assert page.result_code.text() == codigo
        assert page.result_code_row.isVisibleTo(page)
        assert page.result_detail.isVisibleTo(page)
        assert "Venció hace" in page.result_detail.text()
        assert page.photo_slot.isVisibleTo(page)
        assert DANGER in page.result_name.styleSheet()
        assert DANGER not in page.result_detail.styleSheet()
        assert TEXT in page.result_code.styleSheet()
        assert TEXT in page.result_detail.styleSheet()

    def test_codigo_inexistente(self, qtbot, window):
        page = self._page(qtbot, window)
        page.code_input.setText("99999")

        assert "No encontramos" in page.result_name.text()
        assert page.result_name.isVisibleTo(page)
        assert DANGER in page.result_name.styleSheet()
        assert page.photo_slot.isVisibleTo(page)
        assert page.photo_slot.pixmap() is None or page.photo_slot.pixmap().isNull()
        assert not page.result_code_row.isVisibleTo(page)
        assert not page.result_detail.isVisibleTo(page)

    def test_socio_sin_membresia(self, qtbot, window):
        member_id = alta("Nuevo Sanchez")
        codigo = service.get_member(member_id).code

        page = self._page(qtbot, window)
        page.code_input.setText(codigo)

        assert page.result_name.text() == "Nuevo Sanchez"
        assert page.result_name.isVisibleTo(page)
        assert page.result_code.text() == codigo
        assert page.result_code_row.isVisibleTo(page)
        assert page.result_detail.isVisibleTo(page)
        assert "No cuenta" in page.result_detail.text()
        assert page.photo_slot.isVisibleTo(page)
        assert DANGER in page.result_name.styleSheet()
        assert DANGER not in page.result_detail.styleSheet()

    def test_consulta_sola_al_completar_cinco_digitos(self, qtbot, window):
        page = self._page(qtbot, window)
        qtbot.keyClicks(page.code_input, "9999")
        assert not page.result_name.isVisibleTo(page)

        qtbot.keyClicks(page.code_input, "9")
        assert page.result_name.isVisibleTo(page)

    def test_limpia_el_campo_tras_consultar(self, qtbot, window):
        page = self._page(qtbot, window)
        page.code_input.setText("99999")
        assert page.code_input.text() == ""

    def test_teclear_de_nuevo_limpia_el_resultado(self, qtbot, window):
        page = self._page(qtbot, window)
        page.code_input.setText("99999")
        assert page.result_name.isVisibleTo(page)

        qtbot.keyClick(page.code_input, Qt.Key.Key_1)
        assert page.result_name.text() == ""
        self._assert_idle(page)

    def test_el_cuadro_de_resultado_esta_vacio_al_inicio(self, qtbot, window):
        page = self._page(qtbot, window)
        self._assert_idle(page)

    def test_saludo_usa_el_nombre_del_gimnasio(self, qtbot, window):
        page = self._page(qtbot, window)
        assert page.heading.text() == "Gimnasio de Prueba"
        assert page.heading.parentWidget() is not page.input_card
        assert page.instruction.parentWidget() is not page.input_card
        assert page.instruction.text() == "Ingresa tu código de 5 dígitos"

    def test_muestra_la_direccion_si_esta_configurada(self, qtbot, window):
        window.settings.gym_address = "Calle 8 #120"
        page = self._page(qtbot, window)

        assert page.address.isVisibleTo(page)
        assert page.address.text() == "Calle 8 #120"

    def test_oculta_la_direccion_si_esta_vacia(self, qtbot, window):
        window.settings.gym_address = ""
        page = self._page(qtbot, window)
        assert not page.address.isVisibleTo(page)

    def test_muestra_reloj_y_fecha(self, qtbot, window):
        page = self._page(qtbot, window)
        assert page.clock_time.text()
        assert page.clock_date.text()

    def test_casillas_reflejan_los_digitos(self, qtbot, window):
        page = self._page(qtbot, window)
        qtbot.keyClicks(page.code_input, "12")
        assert page.code_input.text() == "12"

    def test_resultado_vigente_muestra_codigo_y_no_el_plan(self, qtbot, window, app_catalog):
        member_id = alta("Ana Lopez")
        dar_periodo(member_id, app_catalog, dias=10)
        codigo = service.get_member(member_id).code

        page = self._page(qtbot, window)
        page.code_input.setText(codigo)

        assert page.result_name.text() == "Ana Lopez"
        assert page.result_code_label.text() == "Código:"
        assert page.result_code.text() == codigo
        assert page.result_code_row.isVisibleTo(page)
        assert "General" not in page.result_code.text()
        assert "Mensual" not in page.result_code.text()
        assert page.result_detail.isVisibleTo(page)
        assert "Vence en" in page.result_detail.text()
        assert page.photo_slot.isVisibleTo(page)
        assert SUCCESS in page.result_name.styleSheet()
        assert SUCCESS not in page.result_detail.styleSheet()
        assert TEXT in page.result_code.styleSheet()
        assert TEXT in page.result_detail.styleSheet()

    def test_enter_con_codigo_corto_consulta(self, qtbot, window):
        page = self._page(qtbot, window)
        qtbot.keyClicks(page.code_input, "1234")
        qtbot.keyClick(page.code_input, Qt.Key.Key_Return)

        assert "5 dígitos" in page.result_name.text()
        assert page.result_name.isVisibleTo(page)
        assert DANGER in page.result_name.styleSheet()

    def test_las_letras_no_entran_al_codigo(self, qtbot, window):
        page = self._page(qtbot, window)
        qtbot.keyClicks(page.code_input, "12ab3")
        assert page.code_input.text() == "123"

    def test_refresh_vuelve_al_reposo(self, qtbot, window):
        page = self._page(qtbot, window)
        page.code_input.setText("99999")
        assert page.result_name.isVisibleTo(page)

        page.refresh()
        self._assert_idle(page)

    def test_el_timer_limpia_el_resultado(self, qtbot, window):
        page = self._page(qtbot, window)
        page.code_input.setText("99999")

        assert page._reset_timer.isActive()
        assert page._reset_timer.interval() == RESULT_HOLD_MS

        page._reset_timer.timeout.emit()
        self._assert_idle(page)


class TestKioskClock:
    def test_medianoche(self):
        time_text, date_text = _clock_parts(datetime(2026, 9, 12, 0, 5))
        assert time_text == "12:05 a.m."
        assert date_text == "Sábado 12 Sep 2026"

    def test_mediodia(self):
        time_text, _ = _clock_parts(datetime(2026, 9, 12, 12, 0))
        assert time_text == "12:00 p.m."
