
"""
Kiem thu tich hop bang chung Module 2 -> Module 3.

Muc tieu:
- Neu khong mo duoc anh nguon M2,
  khong duoc goi service tao Ticket M3.
- Khong su dung database that.
- Khong thay doi Smart Routing hoac SLA.
"""

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .attachment_integration import (
    tao_ticket_kem_bang_chung,
)


class AttachmentIntegrationTest(SimpleTestCase):

    @patch(
        "chatbot.attachment_integration.tao_ticket_theo_chuan_m3"
    )
    @patch(
        "chatbot.attachment_integration.chuan_bi_file_gui_m3"
    )
    @patch(
        "chatbot.attachment_integration.chuan_bi_bang_chung_cho_m3"
    )
    def test_missing_source_does_not_create_ticket(
        self,
        mock_chuan_bi,
        mock_mo_file,
        mock_tao_ticket,
    ):
        yeu_cau = {
            "ma_khach_hang": 1,
            "bang_chung": [
                {
                    "ten_goc": "anh_loi.jpg",
                    "duong_dan_luu": "kh_1/abc.jpg",
                    "dung_luong": 1000,
                }
            ],
        }

        mock_chuan_bi.return_value = yeu_cau["bang_chung"]

        mock_mo_file.side_effect = ValidationError(
            "Khong tim thay file bang chung M2."
        )

        with self.assertRaises(ValidationError):
            tao_ticket_kem_bang_chung(
                yeu_cau=yeu_cau,
                khach_hang=object(),
                danh_muc=object(),
            )

        # Service M3 khong duoc goi neu anh nguon loi.
        mock_tao_ticket.assert_not_called()


    @patch(
        "chatbot.attachment_integration.luu_anh_bang_chung_ticket"
    )
    @patch(
        "chatbot.attachment_integration.tao_ticket_theo_chuan_m3"
    )
    @patch(
        "chatbot.attachment_integration.chuan_bi_file_gui_m3"
    )
    @patch(
        "chatbot.attachment_integration.chuan_bi_bang_chung_cho_m3"
    )
    def test_retry_reuses_ticket_and_processes_evidence(
        self,
        mock_chuan_bi,
        mock_mo_file,
        mock_tao_ticket,
        mock_luu_anh,
    ):
        from contextlib import nullcontext
        from unittest.mock import Mock

        yeu_cau = {
            "ma_khach_hang": 1,
            "bang_chung": [
                {
                    "ten_goc": "anh_1.jpg",
                    "duong_dan_luu": "kh_1/anh_1.jpg",
                    "dung_luong": 1000,
                },
                {
                    "ten_goc": "anh_2.jpg",
                    "duong_dan_luu": "kh_1/anh_2.jpg",
                    "dung_luong": 1000,
                },
            ],
        }

        khach_hang = Mock()
        danh_muc = Mock()
        ticket_cu = Mock()

        # Mo phong M2 da kiem tra hai anh nguon.
        mock_chuan_bi.return_value = yeu_cau["bang_chung"]

        tep_1 = Mock(name="tep_1")
        tep_2 = Mock(name="tep_2")

        mock_mo_file.return_value = nullcontext(
            [tep_1, tep_2]
        )

        # M3 tra ve Ticket cu theo source_request_id.
        mock_tao_ticket.return_value = ticket_cu

        # Service M3 tu xu ly trung anh nguon.
        mock_luu_anh.side_effect = [
            Mock(name="anh_da_co"),
            Mock(name="anh_moi"),
        ]

        ket_qua = tao_ticket_kem_bang_chung(
            yeu_cau=yeu_cau,
            khach_hang=khach_hang,
            danh_muc=danh_muc,
        )

        self.assertIs(ket_qua, ticket_cu)

        mock_tao_ticket.assert_called_once_with(
            yeu_cau=yeu_cau,
            khach_hang=khach_hang,
            danh_muc=danh_muc,
        )

        self.assertEqual(
            mock_luu_anh.call_count,
            2,
        )

        self.assertEqual(
            mock_luu_anh.call_args_list[0].kwargs[
                "ma_anh_nguon"
            ],
            "kh_1/anh_1.jpg",
        )

        self.assertEqual(
            mock_luu_anh.call_args_list[1].kwargs[
                "ma_anh_nguon"
            ],
            "kh_1/anh_2.jpg",
        )


    @patch(
        "chatbot.attachment_integration.luu_anh_bang_chung_ticket"
    )
    @patch(
        "chatbot.attachment_integration.tao_ticket_theo_chuan_m3"
    )
    @patch(
        "chatbot.attachment_integration.chuan_bi_file_gui_m3"
    )
    @patch(
        "chatbot.attachment_integration.chuan_bi_bang_chung_cho_m3"
    )
    def test_second_image_failure_stops_submission(
        self,
        mock_chuan_bi,
        mock_mo_file,
        mock_tao_ticket,
        mock_luu_anh,
    ):
        from contextlib import nullcontext
        from unittest.mock import Mock

        yeu_cau = {
            "ma_khach_hang": 1,
            "bang_chung": [
                {"duong_dan_luu": "kh_1/anh_1.jpg"},
                {"duong_dan_luu": "kh_1/anh_2.jpg"},
                {"duong_dan_luu": "kh_1/anh_3.jpg"},
            ],
        }

        mock_chuan_bi.return_value = yeu_cau["bang_chung"]

        mock_mo_file.return_value = nullcontext(
            [Mock(), Mock(), Mock()]
        )

        mock_tao_ticket.return_value = Mock()

        # Anh 1 thanh cong, anh 2 that bai.
        mock_luu_anh.side_effect = [
            Mock(),
            ValidationError("Khong the luu anh thu hai."),
        ]

        with self.assertRaises(ValidationError):
            tao_ticket_kem_bang_chung(
                yeu_cau=yeu_cau,
                khach_hang=Mock(),
                danh_muc=Mock(),
            )

        # Dung ngay khi anh thu hai loi.
        self.assertEqual(mock_luu_anh.call_count, 2)

        # Anh thu ba chua duoc xu ly.
        self.assertEqual(
            mock_luu_anh.call_args_list[-1].kwargs[
                "ma_anh_nguon"
            ],
            "kh_1/anh_2.jpg",
        )

        # Ham dieu phoi khong tra ve thanh cong.
        mock_tao_ticket.assert_called_once()


from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage

from chatbot.integration_m3 import gui_yeu_cau_sang_m3


class M2M3SubmissionFailureTest(SimpleTestCase):

    @patch("chatbot.integration_m3.redirect")
    @patch("chatbot.integration_m3.tao_ticket_kem_bang_chung")
    @patch("chatbot.integration_m3.TicketCategory.objects.filter")
    @patch("chatbot.integration_m3.YeuCauHoTroForm")
    @patch("chatbot.integration_m3.Customer.objects.filter")
    def test_failure_keeps_m2_draft(
        self,
        mock_customer_filter,
        mock_form,
        mock_category_filter,
        mock_send,
        mock_redirect,
    ):
        from unittest.mock import Mock

        customer = Mock()
        customer.pk = 1

        mock_customer_filter.return_value.first.return_value = customer
        mock_form.return_value.is_valid.return_value = True
        mock_category_filter.return_value.first.return_value = Mock()

        mock_send.side_effect = ValidationError(
            "Luu bang chung that bai"
        )

        request = RequestFactory().post(
            "/chatbot/gui-yeu-cau-sang-m3/"
        )

        user = Mock()
        user.is_authenticated = True
        request.user = user

        draft = {
            "ma_khach_hang": 1,
            "loai_van_de": "SAN_PHAM_LOI",
            "thong_tin": {"mo_ta": "San pham bi hong"},
            "bang_chung": [
                {"ten_goc": "anh_1.jpg"}
            ],
        }

        request.session = {
            "m2_yeu_cau_ho_tro": draft
        }

        request._messages = FallbackStorage(request)

        mock_redirect.return_value = Mock()

        gui_yeu_cau_sang_m3(request)

        self.assertEqual(
            request.session["m2_yeu_cau_ho_tro"],
            draft,
        )

        self.assertNotIn(
            "m2_ticket_vua_tao",
            request.session,
        )

        mock_send.assert_called_once()
        mock_redirect.assert_called_once_with(
            "chatbot:xac_nhan_yeu_cau"
        )


    @patch("chatbot.integration_m3.redirect")
    @patch("chatbot.integration_m3.tao_ticket_kem_bang_chung")
    @patch("chatbot.integration_m3.TicketCategory.objects.filter")
    @patch("chatbot.integration_m3.YeuCauHoTroForm")
    @patch("chatbot.integration_m3.Customer.objects.filter")
    def test_success_clears_draft_only_after_service_returns(
        self,
        mock_customer_filter,
        mock_form,
        mock_category_filter,
        mock_send,
        mock_redirect,
    ):
        from unittest.mock import Mock

        customer = Mock()
        customer.pk = 1

        mock_customer_filter.return_value.first.return_value = customer
        mock_form.return_value.is_valid.return_value = True
        mock_category_filter.return_value.first.return_value = Mock()

        draft = {
            "ma_khach_hang": 1,
            "loai_van_de": "SAN_PHAM_LOI",
            "thong_tin": {"mo_ta": "San pham bi hong"},
            "bang_chung": [{"ten_goc": "anh_1.jpg"}],
        }

        request = RequestFactory().post(
            "/chatbot/gui-yeu-cau-sang-m3/"
        )

        user = Mock()
        user.is_authenticated = True
        request.user = user

        request.session = {
            "m2_yeu_cau_ho_tro": draft
        }

        # Dung RequestFactory nen can gan message storage.
        from django.contrib.messages.storage.base import BaseStorage

        class TestMessageStorage(BaseStorage):
            def _get(self, *args, **kwargs):
                return [], True

            def _store(self, messages, response, *args, **kwargs):
                return []

        request._messages = TestMessageStorage(request)

        ticket = Mock()
        ticket.pk = 15
        ticket.ma_ticket = "TK_TEST_015"

        def gui_thanh_cong(**kwargs):
            # Khi service dang xu ly, ban nhap van phai ton tai.
            self.assertIn(
                "m2_yeu_cau_ho_tro",
                request.session,
            )
            return ticket

        mock_send.side_effect = gui_thanh_cong
        mock_redirect.return_value = Mock()

        gui_yeu_cau_sang_m3(request)

        self.assertNotIn(
            "m2_yeu_cau_ho_tro",
            request.session,
        )

        self.assertEqual(
            request.session["m2_ticket_vua_tao"],
            {
                "ticket_id": 15,
                "ma_ticket": "TK_TEST_015",
            },
        )

        mock_send.assert_called_once()
        mock_redirect.assert_called_once_with(
            "chatbot:home"
        )

class M2RealFileHandoffTest(SimpleTestCase):

    @patch(
        "chatbot.attachment_integration.luu_anh_bang_chung_ticket"
    )
    @patch(
        "chatbot.attachment_integration.tao_ticket_theo_chuan_m3"
    )
    def test_real_jpeg_reaches_m3_with_correct_content(
        self,
        mock_create_ticket,
        mock_save_attachment,
    ):
        from io import BytesIO
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from uuid import uuid4

        from PIL import Image
        from django.test import override_settings

        from chatbot.attachment_integration import (
            tao_ticket_kem_bang_chung,
        )

        with TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "CRM_HULO"
            base_dir.mkdir()

            source_folder = (
                Path(temp_dir)
                / "CRM_HULO_m2_private"
                / "kh_1"
            )
            source_folder.mkdir(parents=True)

            # Tao anh JPEG that trong bo nho.
            image_buffer = BytesIO()
            Image.new(
                "RGB",
                (100, 100),
                "white",
            ).save(image_buffer, format="JPEG")

            image_content = image_buffer.getvalue()

            source_name = f"kh_1/{uuid4().hex}.jpg"
            source_path = (
                Path(temp_dir)
                / "CRM_HULO_m2_private"
                / source_name
            )
            source_path.write_bytes(image_content)

            draft = {
                "ma_khach_hang": 1,
                "source_request_id": "TEST_M2_M3_IMAGE",
                "bang_chung": [
                    {
                        "ten_goc": "san_pham_hong.jpg",
                        "duong_dan_luu": source_name,
                        "dung_luong": len(image_content),
                    }
                ],
            }

            customer = SimpleNamespace(pk=1)
            category = object()
            ticket = SimpleNamespace(pk=123)

            mock_create_ticket.return_value = ticket

            received_files = []

            def capture_attachment(**kwargs):
                file_obj = kwargs["tep"]

                received_files.append({
                    "name": file_obj.name,
                    "content": file_obj.read(),
                    "source": kwargs["ma_anh_nguon"],
                })

                return object()

            mock_save_attachment.side_effect = capture_attachment

            with override_settings(BASE_DIR=base_dir):
                result = tao_ticket_kem_bang_chung(
                    yeu_cau=draft,
                    khach_hang=customer,
                    danh_muc=category,
                )

            self.assertIs(result, ticket)

            mock_create_ticket.assert_called_once()
            mock_save_attachment.assert_called_once()

            self.assertEqual(len(received_files), 1)

            self.assertEqual(
                received_files[0]["name"],
                "san_pham_hong.jpg",
            )

            self.assertEqual(
                received_files[0]["content"],
                image_content,
            )

            self.assertEqual(
                received_files[0]["source"],
                source_name,
            )
