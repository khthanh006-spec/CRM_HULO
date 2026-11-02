
"""
Kiem thu viec luu anh TicketAttachment.

Su dung TransactionTestCase de kiem tra:
- Loi database khong tao file.
- Rollback transaction ngoai khong tao file.
- Gui lai cung anh nguon khong tao trung.
- Gui lai sau khi co anh loi chi luu anh con thieu.
"""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import TransactionTestCase, override_settings

from PIL import Image

from customers.models import Customer
from .attachment_services import luu_anh_bang_chung_ticket
from .models import Ticket, TicketAttachment


class AttachmentFailureTest(TransactionTestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="khachhang_test_attachment",
            password="TestPassword123!",
        )

        self.khach_hang = Customer.objects.create(
            ma_tai_khoan=self.user,
            ho_ten="Khach hang kiem thu",
            email="attachment-test@example.com",
        )

        self.ticket = Ticket.objects.create(
            ma_ticket="TK-TEST-ATTACHMENT-001",
            source_request_id="TEST-ATTACHMENT-001",
            khach_hang=self.khach_hang,
            tieu_de="Kiem thu luu bang chung",
            noi_dung="Kiem tra xu ly loi database.",
            trang_thai="IN_PROGRESS",
        )

    def tao_anh(self, ten="anh.jpg", hop_le=True):
        bo_nho = BytesIO()

        if hop_le:
            Image.new(
                "RGB", (100, 100), "white"
            ).save(bo_nho, format="JPEG")
            noi_dung = bo_nho.getvalue()
        else:
            noi_dung = b"Day khong phai anh JPEG"

        return SimpleUploadedFile(
            ten,
            noi_dung,
            content_type="image/jpeg",
        )

    def danh_sach_file(self, thu_muc):
        return [
            tep
            for tep in Path(thu_muc).rglob("*")
            if tep.is_file()
        ]

    def test_database_failure_does_not_leave_file(self):
        with TemporaryDirectory() as thu_muc:
            with override_settings(MEDIA_ROOT=thu_muc):
                with patch.object(
                    TicketAttachment,
                    "save",
                    autospec=True,
                    side_effect=DatabaseError(
                        "Gia lap loi database"
                    ),
                ) as mock_save:

                    with self.assertRaises(DatabaseError):
                        luu_anh_bang_chung_ticket(
                            ticket=self.ticket,
                            khach_hang=self.khach_hang,
                            tep=self.tao_anh(),
                        )

                self.assertEqual(mock_save.call_count, 1)

                self.assertEqual(
                    TicketAttachment.objects.filter(
                        ticket=self.ticket
                    ).count(),
                    0,
                )

                self.assertEqual(
                    self.danh_sach_file(thu_muc),
                    [],
                )

    def test_outer_transaction_rollback(self):
        with TemporaryDirectory() as thu_muc:
            with override_settings(MEDIA_ROOT=thu_muc):

                with self.assertRaises(RuntimeError):
                    with transaction.atomic():
                        luu_anh_bang_chung_ticket(
                            ticket=self.ticket,
                            khach_hang=self.khach_hang,
                            tep=self.tao_anh(),
                        )

                        raise RuntimeError(
                            "Gia lap rollback ben ngoai"
                        )

                self.assertEqual(
                    TicketAttachment.objects.filter(
                        ticket=self.ticket
                    ).count(),
                    0,
                )

                self.assertEqual(
                    self.danh_sach_file(thu_muc),
                    [],
                    "Transaction rollback nhung file anh van con!",
                )

    def test_same_source_does_not_create_duplicate_attachment(self):
        ma_nguon = (
            f"kh_{self.khach_hang.pk}/"
            f"{'a' * 32}.jpg"
        )

        with TemporaryDirectory() as thu_muc:
            with override_settings(MEDIA_ROOT=thu_muc):

                anh_1 = luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.khach_hang,
                    tep=self.tao_anh("anh_1.jpg"),
                    ma_anh_nguon=ma_nguon,
                )

                anh_2 = luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.khach_hang,
                    tep=self.tao_anh("anh_1.jpg"),
                    ma_anh_nguon=ma_nguon,
                )

                self.assertEqual(anh_1.pk, anh_2.pk)

                self.assertEqual(
                    TicketAttachment.objects.filter(
                        ticket=self.ticket
                    ).count(),
                    1,
                )

                self.assertEqual(
                    len(self.danh_sach_file(thu_muc)),
                    1,
                )

                anh_1.refresh_from_db()
                self.assertTrue(
                    anh_1.tep_dinh_kem.storage.exists(
                        anh_1.tep_dinh_kem.name
                    )
                )

    def test_retry_saves_only_missing_attachment(self):
        ma_nguon_1 = (
            f"kh_{self.khach_hang.pk}/"
            f"{'a' * 32}.jpg"
        )

        ma_nguon_2 = (
            f"kh_{self.khach_hang.pk}/"
            f"{'b' * 32}.jpg"
        )

        with TemporaryDirectory() as thu_muc:
            with override_settings(MEDIA_ROOT=thu_muc):

                anh_1 = luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.khach_hang,
                    tep=self.tao_anh("anh_1.jpg"),
                    ma_anh_nguon=ma_nguon_1,
                )

                with self.assertRaises(Exception):
                    luu_anh_bang_chung_ticket(
                        ticket=self.ticket,
                        khach_hang=self.khach_hang,
                        tep=self.tao_anh(
                            "anh_2.jpg",
                            hop_le=False,
                        ),
                        ma_anh_nguon=ma_nguon_2,
                    )

                anh_1_gui_lai = luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.khach_hang,
                    tep=self.tao_anh("anh_1.jpg"),
                    ma_anh_nguon=ma_nguon_1,
                )

                anh_2 = luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.khach_hang,
                    tep=self.tao_anh("anh_2.jpg"),
                    ma_anh_nguon=ma_nguon_2,
                )

                self.assertEqual(
                    anh_1.pk,
                    anh_1_gui_lai.pk,
                )

                self.assertNotEqual(
                    anh_1.pk,
                    anh_2.pk,
                )

                self.assertEqual(
                    TicketAttachment.objects.filter(
                        ticket=self.ticket
                    ).count(),
                    2,
                )

                self.assertEqual(
                    len(self.danh_sach_file(thu_muc)),
                    2,
                )
