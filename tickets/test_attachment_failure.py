
"""
Kiem thu loi database khi luu anh TicketAttachment.

- Tao Customer va Ticket trong database test.
- Gia lap loi khi luu ban ghi TicketAttachment.
- Kiem tra file anh da duoc don dep.
- Khong su dung Ticket va kho anh that.
"""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings

from PIL import Image

from customers.models import Customer

from .attachment_services import luu_anh_bang_chung_ticket
from .models import Ticket, TicketAttachment


class AttachmentFailureTest(TestCase):

    def setUp(self):
        # 1. Tao tai khoan khach hang trong database test
        User = get_user_model()

        self.user = User.objects.create_user(
            username="khachhang_test_attachment",
            password="TestPassword123!",
        )

        # 2. Tao ho so Customer
        self.khach_hang = Customer.objects.create(
            ma_tai_khoan=self.user,
            ho_ten="Khach hang kiem thu",
            email="attachment-test@example.com",
        )

        # 3. Tao Ticket mau, khong goi Smart Routing
        self.ticket = Ticket.objects.create(
            ma_ticket="TK-TEST-ATTACHMENT-001",
            source_request_id="TEST-ATTACHMENT-001",
            khach_hang=self.khach_hang,
            tieu_de="Kiem thu luu bang chung",
            noi_dung="Kiem tra xu ly loi database.",
            trang_thai="IN_PROGRESS",
            ket_qua_xu_ly="",
            ly_do_khong_dong_y="",
        )

    def test_database_failure_does_not_leave_file(self):
        # 4. Tao anh JPEG that trong bo nho
        bo_nho = BytesIO()

        Image.new(
            "RGB",
            (100, 100),
            "white",
        ).save(
            bo_nho,
            format="JPEG",
        )

        tep = SimpleUploadedFile(
            "anh_kiem_thu.jpg",
            bo_nho.getvalue(),
            content_type="image/jpeg",
        )

        so_anh_truoc = TicketAttachment.objects.filter(
            ticket=self.ticket
        ).count()

        # 5. Su dung thu muc rieng cho anh kiem thu
        with TemporaryDirectory() as thu_muc_tam:

            with override_settings(MEDIA_ROOT=thu_muc_tam):

                # 6. Gia lap loi database tai dung thao tac
                # luu ban ghi TicketAttachment
                with patch.object(
                    TicketAttachment,
                    "save",
                    autospec=True,
                    side_effect=DatabaseError(
                        "Loi database gia lap"
                    ),
                ) as mock_save:

                    with self.assertRaises(DatabaseError):
                        luu_anh_bang_chung_ticket(
                            ticket=self.ticket,
                            khach_hang=self.khach_hang,
                            tep=tep,
                        )

                    # Bao dam test thuc su da di den buoc
                    # ghi database, khong bi chan o buoc truoc.
                    mock_save.assert_called_once()

                # 7. Kiem tra khong con file trong kho tam
                tep_con_lai = [
                    p for p in Path(thu_muc_tam).rglob("*")
                    if p.is_file()
                ]

                self.assertEqual(
                    tep_con_lai,
                    [],
                    "Van con file sau khi luu database that bai.",
                )

        # 8. Kiem tra database khong phat sinh ban ghi
        so_anh_sau = TicketAttachment.objects.filter(
            ticket=self.ticket
        ).count()

        self.assertEqual(
            so_anh_truoc,
            so_anh_sau,
        )

        # 9. Kiem tra Ticket khong bi thay doi
        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.trang_thai,
            "IN_PROGRESS",
        )


    def test_outer_transaction_rollback(self):
        """
        Kiem tra file sau khi transaction ben ngoai rollback.

        Test nay dung de phat hien file mo coi.
        Voi service hien tai, test co the FAIL.
        """

        bo_nho = BytesIO()

        Image.new(
            "RGB", (100, 100), "white"
        ).save(bo_nho, format="JPEG")

        tep = SimpleUploadedFile(
            "anh_rollback.jpg",
            bo_nho.getvalue(),
            content_type="image/jpeg",
        )

        with TemporaryDirectory() as thu_muc_tam:
            with override_settings(MEDIA_ROOT=thu_muc_tam):

                try:
                    with transaction.atomic():
                        luu_anh_bang_chung_ticket(
                            ticket=self.ticket,
                            khach_hang=self.khach_hang,
                            tep=tep,
                        )

                        # Gia lap loi sau khi service da luu anh
                        raise RuntimeError("Gia lap rollback")

                except RuntimeError:
                    pass

                # Database phai khong con ban ghi anh
                self.assertFalse(
                    TicketAttachment.objects.filter(
                        ticket=self.ticket
                    ).exists()
                )

                # Kiem tra file vat ly co bi bo lai khong
                cac_file = [
                    p for p in Path(thu_muc_tam).rglob("*")
                    if p.is_file()
                ]

                self.assertEqual(
                    cac_file,
                    [],
                    "Transaction rollback nhung file anh van con!",
                )


    def test_same_source_does_not_create_duplicate_attachment(self):
        """
        Gui lai cung ma anh nguon:
        - Chi co mot TicketAttachment.
        - Khong tao them file.
        - Giu nguyen Ticket.
        """

        from uuid import uuid4

        bo_nho = BytesIO()

        Image.new(
            "RGB",
            (100, 100),
            "white",
        ).save(
            bo_nho,
            format="JPEG",
        )

        noi_dung_anh = bo_nho.getvalue()

        ma_nguon = (
            f"kh_{self.khach_hang.pk}/"
            f"{uuid4().hex}.jpg"
        )

        with TemporaryDirectory() as thu_muc_tam:
            with override_settings(MEDIA_ROOT=thu_muc_tam):

                anh_1 = luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.khach_hang,
                    tep=SimpleUploadedFile(
                        "anh_1.jpg",
                        noi_dung_anh,
                    ),
                    ma_anh_nguon=ma_nguon,
                )

                anh_2 = luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.khach_hang,
                    tep=SimpleUploadedFile(
                        "anh_1.jpg",
                        noi_dung_anh,
                    ),
                    ma_anh_nguon=ma_nguon,
                )

                self.assertEqual(anh_1.pk, anh_2.pk)

                self.assertEqual(
                    TicketAttachment.objects.filter(
                        ticket=self.ticket
                    ).count(),
                    1,
                )

                cac_file = [
                    p for p in Path(thu_muc_tam).rglob("*")
                    if p.is_file()
                ]

                self.assertEqual(
                    len(cac_file),
                    1,
                )

                self.ticket.refresh_from_db()

                self.assertEqual(
                    self.ticket.trang_thai,
                    "IN_PROGRESS",
                )


    def test_retry_saves_only_missing_attachment(self):
        """
        Anh 1 luu thanh cong.
        Anh 2 bi loi.
        Gui lai: chi bo sung anh 2.
        """

        from uuid import uuid4
        from django.core.exceptions import ValidationError

        bo_nho = BytesIO()
        Image.new("RGB", (100, 100), "white").save(
            bo_nho, format="JPEG"
        )
        noi_dung_anh = bo_nho.getvalue()

        ma_nguon_1 = f"kh_{self.khach_hang.pk}/{uuid4().hex}.jpg"
        ma_nguon_2 = f"kh_{self.khach_hang.pk}/{uuid4().hex}.jpg"

        with TemporaryDirectory() as thu_muc_tam:
            with override_settings(MEDIA_ROOT=thu_muc_tam):

                # Lan gui dau: anh 1 thanh cong
                anh_1 = luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.khach_hang,
                    tep=SimpleUploadedFile(
                        "anh_1.jpg", noi_dung_anh
                    ),
                    ma_anh_nguon=ma_nguon_1,
                )

                # Anh 2 bi loi: file khong phai JPEG
                with self.assertRaises(ValidationError):
                    luu_anh_bang_chung_ticket(
                        ticket=self.ticket,
                        khach_hang=self.khach_hang,
                        tep=SimpleUploadedFile(
                            "anh_2.jpg", b"anh-gia"
                        ),
                        ma_anh_nguon=ma_nguon_2,
                    )

                self.assertEqual(
                    TicketAttachment.objects.filter(
                        ticket=self.ticket
                    ).count(),
                    1,
                )

                # Gui lai: anh 1 duoc nhan dien da ton tai
                anh_1_gui_lai = luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.khach_hang,
                    tep=SimpleUploadedFile(
                        "anh_1.jpg", noi_dung_anh
                    ),
                    ma_anh_nguon=ma_nguon_1,
                )

                self.assertEqual(
                    anh_1.pk,
                    anh_1_gui_lai.pk,
                )

                # Gui lai anh 2 hop le
                anh_2 = luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.khach_hang,
                    tep=SimpleUploadedFile(
                        "anh_2.jpg", noi_dung_anh
                    ),
                    ma_anh_nguon=ma_nguon_2,
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

                cac_file = [
                    p for p in Path(thu_muc_tam).rglob("*")
                    if p.is_file()
                ]

                self.assertEqual(len(cac_file), 2)

                # Khong doi trang thai Ticket
                self.ticket.refresh_from_db()
                self.assertEqual(
                    self.ticket.trang_thai,
                    "IN_PROGRESS",
                )
