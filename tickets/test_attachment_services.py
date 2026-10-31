
"""
MODULE 3 - ATTACHMENT SERVICE TESTS

Kiểm thử:
- Lưu ảnh JPEG hợp lệ.
- Từ chối file giả JPEG.
- Kiểm tra giới hạn dung lượng và pixel.
- Kiểm tra giới hạn 5 ảnh/Ticket.
- Chống lưu trùng ảnh nguồn.
- Kiểm tra quyền sở hữu Ticket.
- Kiểm tra transaction rollback.
- Kiểm tra lỗi Storage.
- Đảm bảo không thay đổi trạng thái Ticket.
"""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TransactionTestCase, override_settings

from PIL import Image

from accounts.models import Staff
from customers.models import Customer

from .attachment_services import (
    DUNG_LUONG_TOI_DA,
    luu_anh_bang_chung_ticket,
)
from .models import Ticket, TicketAttachment


class TicketAttachmentServiceTest(TransactionTestCase):

    def setUp(self):

        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.settings_override = override_settings(
            MEDIA_ROOT=self.temp_dir.name
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        User = get_user_model()

        self.user = User.objects.create_user(
            username="attachment_customer",
            password="TestPassword123!",
        )

        self.customer = Customer.objects.create(
            ma_tai_khoan=self.user,
            ho_ten="Khach hang kiem thu",
            email="attachment_customer@example.com",
        )

        self.staff_user = User.objects.create_user(
            username="attachment_staff",
            password="TestPassword123!",
        )

        self.staff = Staff.objects.create(
            ma_tai_khoan=self.staff_user,
            ho_ten="Nhan vien CSKH",
            vai_tro="CSKH",
        )

        self.ticket = Ticket.objects.create(
            ma_ticket="TK_ATTACHMENT_TEST_001",
            source_request_id="SOURCE_ATTACHMENT_TEST_001",
            khach_hang=self.customer,
            tieu_de="Kiem thu bang chung",
            noi_dung="Kiem tra Attachment Service",
            muc_uu_tien="MEDIUM",
            trang_thai="IN_PROGRESS",
            nguoi_phu_trach=self.staff,
            ket_qua_xu_ly="Dang kiem tra",
        )

    # ==========================================
    # HELPER
    # ==========================================

    def tao_anh_jpeg(self, ten="anh_test.jpg"):

        buffer = BytesIO()

        Image.new(
            "RGB",
            (100, 100),
            "white",
        ).save(
            buffer,
            format="JPEG",
        )

        return SimpleUploadedFile(
            ten,
            buffer.getvalue(),
            content_type="image/jpeg",
        )

    def tao_ma_anh_nguon(self):

        return (
            f"kh_{self.customer.pk}/"
            f"{uuid4().hex}.jpg"
        )

    def danh_sach_file(self):

        return [
            path
            for path in Path(self.temp_dir.name).rglob("*")
            if path.is_file()
        ]

    # ==========================================
    # TEST 1 - LUU ANH THANH CONG
    # ==========================================

    def test_save_valid_jpeg(self):

        anh = self.tao_anh_jpeg()

        attachment = luu_anh_bang_chung_ticket(
            ticket=self.ticket,
            khach_hang=self.customer,
            tep=anh,
        )

        attachment.refresh_from_db()

        self.assertTrue(
            attachment.tep_dinh_kem.name
        )

        self.assertTrue(
            attachment.tep_dinh_kem.storage.exists(
                attachment.tep_dinh_kem.name
            )
        )

        self.assertEqual(
            TicketAttachment.objects.filter(
                ticket=self.ticket
            ).count(),
            1,
        )

    # ==========================================
    # TEST 2 - TU CHOI DUOI FILE KHONG HOP LE
    # ==========================================

    def test_reject_invalid_extension(self):

        tep = SimpleUploadedFile(
            "anh.png",
            b"fake-image",
        )

        with self.assertRaises(ValidationError):

            luu_anh_bang_chung_ticket(
                ticket=self.ticket,
                khach_hang=self.customer,
                tep=tep,
            )

        self.assertEqual(
            TicketAttachment.objects.count(),
            0,
        )

    # ==========================================
    # TEST 3 - TU CHOI NOI DUNG GIA JPEG
    # ==========================================

    def test_reject_fake_jpeg(self):

        tep = SimpleUploadedFile(
            "anh_gia.jpg",
            b"this-is-not-a-jpeg",
            content_type="image/jpeg",
        )

        with self.assertRaises(ValidationError):

            luu_anh_bang_chung_ticket(
                ticket=self.ticket,
                khach_hang=self.customer,
                tep=tep,
            )

        self.assertEqual(
            TicketAttachment.objects.count(),
            0,
        )

    # ==========================================
    # TEST 4 - GIOI HAN DUNG LUONG
    # ==========================================

    def test_reject_file_over_10mb(self):

        du_lieu = b"x" * (
            DUNG_LUONG_TOI_DA + 1
        )

        tep = SimpleUploadedFile(
            "anh_qua_lon.jpg",
            du_lieu,
        )

        with self.assertRaises(ValidationError):

            luu_anh_bang_chung_ticket(
                ticket=self.ticket,
                khach_hang=self.customer,
                tep=tep,
            )

        self.assertEqual(
            TicketAttachment.objects.count(),
            0,
        )

    # ==========================================
    # TEST 5 - GIOI HAN PIXEL
    # ==========================================

    def test_reject_image_over_20_million_pixels(self):

        image_mock = MagicMock()

        image_mock.__enter__.return_value = (
            image_mock
        )

        image_mock.format = "JPEG"
        image_mock.width = 5000
        image_mock.height = 5000

        tep = SimpleUploadedFile(
            "anh_qua_nhieu_pixel.jpg",
            b"fake-data-for-mocked-image",
        )

        with patch(
            "tickets.attachment_services.Image.open",
            return_value=image_mock,
        ):

            with self.assertRaises(ValidationError):

                luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.customer,
                    tep=tep,
                )

        self.assertEqual(
            TicketAttachment.objects.count(),
            0,
        )

    # ==========================================
    # TEST 6 - GIOI HAN 5 ANH
    # ==========================================

    def test_maximum_five_attachments(self):

        for index in range(5):

            luu_anh_bang_chung_ticket(
                ticket=self.ticket,
                khach_hang=self.customer,
                tep=self.tao_anh_jpeg(
                    f"anh_{index}.jpg"
                ),
            )

        self.assertEqual(
            TicketAttachment.objects.filter(
                ticket=self.ticket
            ).count(),
            5,
        )

        with self.assertRaises(ValidationError):

            luu_anh_bang_chung_ticket(
                ticket=self.ticket,
                khach_hang=self.customer,
                tep=self.tao_anh_jpeg(
                    "anh_thu_6.jpg"
                ),
            )

        self.assertEqual(
            TicketAttachment.objects.filter(
                ticket=self.ticket
            ).count(),
            5,
        )

        self.assertEqual(
            len(self.danh_sach_file()),
            5,
        )

    # ==========================================
    # TEST 7 - CHONG LUU TRUNG ANH NGUON
    # ==========================================

    def test_same_source_does_not_create_duplicate(self):

        ma_nguon = self.tao_ma_anh_nguon()

        anh_1 = luu_anh_bang_chung_ticket(
            ticket=self.ticket,
            khach_hang=self.customer,
            tep=self.tao_anh_jpeg("anh_1.jpg"),
            ma_anh_nguon=ma_nguon,
        )

        anh_2 = luu_anh_bang_chung_ticket(
            ticket=self.ticket,
            khach_hang=self.customer,
            tep=self.tao_anh_jpeg("anh_1.jpg"),
            ma_anh_nguon=ma_nguon,
        )

        self.assertEqual(
            anh_1.pk,
            anh_2.pk,
        )

        self.assertEqual(
            TicketAttachment.objects.filter(
                ticket=self.ticket
            ).count(),
            1,
        )

        self.assertEqual(
            len(self.danh_sach_file()),
            1,
        )

    # ==========================================
    # TEST 8 - KIEM TRA QUYEN SO HUU
    # ==========================================

    def test_customer_cannot_upload_to_other_ticket(self):

        other_user = get_user_model().objects.create_user(
            username="other_customer",
            password="TestPassword123!",
        )

        other_customer = Customer.objects.create(
            ma_tai_khoan=other_user,
            ho_ten="Khach hang khac",
            email="other_customer@example.com",
        )

        with self.assertRaises(ValidationError):

            luu_anh_bang_chung_ticket(
                ticket=self.ticket,
                khach_hang=other_customer,
                tep=self.tao_anh_jpeg(),
            )

        self.assertEqual(
            TicketAttachment.objects.count(),
            0,
        )

    # ==========================================
    # TEST 9 - TRANSACTION ROLLBACK
    # ==========================================

    def test_outer_transaction_rollback_leaves_no_file(self):

        with self.assertRaises(RuntimeError):

            with transaction.atomic():

                luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.customer,
                    tep=self.tao_anh_jpeg(),
                )

                # Callback on_commit chưa được thực hiện.
                self.assertEqual(
                    TicketAttachment.objects.filter(
                        ticket=self.ticket
                    ).count(),
                    1,
                )

                self.assertEqual(
                    len(self.danh_sach_file()),
                    0,
                )

                raise RuntimeError(
                    "Simulated transaction rollback"
                )

        self.assertEqual(
            TicketAttachment.objects.filter(
                ticket=self.ticket
            ).count(),
            0,
        )

        self.assertEqual(
            len(self.danh_sach_file()),
            0,
        )

    # ==========================================
    # TEST 10 - STORAGE FAILURE
    # ==========================================

    def test_storage_failure_cleans_database_record(self):

        storage = TicketAttachment._meta.get_field(
            "tep_dinh_kem"
        ).storage

        with patch.object(
            storage,
            "save",
            side_effect=OSError(
                "Simulated storage failure"
            ),
        ):

            with self.assertRaises(OSError):

                luu_anh_bang_chung_ticket(
                    ticket=self.ticket,
                    khach_hang=self.customer,
                    tep=self.tao_anh_jpeg(),
                )

        self.assertEqual(
            TicketAttachment.objects.filter(
                ticket=self.ticket
            ).count(),
            0,
        )

        self.assertEqual(
            len(self.danh_sach_file()),
            0,
        )

    # ==========================================
    # TEST 11 - KHONG THAY DOI TICKET
    # ==========================================

    def test_attachment_does_not_change_ticket(self):

        trang_thai_truoc = self.ticket.trang_thai
        nhan_vien_truoc = self.ticket.nguoi_phu_trach_id
        sla_truoc = self.ticket.sla_deadline
        ket_qua_truoc = self.ticket.ket_qua_xu_ly

        luu_anh_bang_chung_ticket(
            ticket=self.ticket,
            khach_hang=self.customer,
            tep=self.tao_anh_jpeg(),
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.trang_thai,
            trang_thai_truoc,
        )

        self.assertEqual(
            self.ticket.nguoi_phu_trach_id,
            nhan_vien_truoc,
        )

        self.assertEqual(
            self.ticket.sla_deadline,
            sla_truoc,
        )

        self.assertEqual(
            self.ticket.ket_qua_xu_ly,
            ket_qua_truoc,
        )
