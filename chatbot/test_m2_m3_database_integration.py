
"""
Kiem thu tich hop M2 -> M3 bang database test va JPEG that.

Khong su dung database hoac anh cua khach hang that.
Khong mock service tao Ticket hay luu TicketAttachment.
"""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from accounts.models import Staff
from customers.models import Customer
from tickets.models import (
    Ticket,
    TicketAttachment,
    TicketCategory,
    TicketQueue,
    SLAConfig,
    TicketLog,
)

from chatbot.attachment_integration import (
    tao_ticket_kem_bang_chung,
)


class M2M3DatabaseIntegrationTest(TestCase):

    def setUp(self):
        # 1. Tao kho file rieng cho bai test.
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        root = Path(self.temp_dir.name)

        base_dir = root / "CRM_HULO"
        base_dir.mkdir()

        media_root = root / "CRM_HULO_m3_private"
        media_root.mkdir()

        self.settings_override = override_settings(
            BASE_DIR=base_dir,
            MEDIA_ROOT=str(media_root),
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        # 2. Tao khach hang kiem thu.
        User = get_user_model()

        user = User.objects.create_user(
            username="test_m2_m3_customer",
            password="TestPass123!",
        )

        self.customer = Customer.objects.create(
            ma_tai_khoan=user,
            ho_ten="Khach hang HULO Test",
            email="hulo_test@example.com",
        )

        # 3. Tao nhan vien CSKH san sang nhan viec.
        staff_user = User.objects.create_user(
            username="test_m2_m3_staff",
            password="TestPass123!",
        )

        self.staff = Staff.objects.create(
            ma_tai_khoan=staff_user,
            ho_ten="CSKH San pham Test",
            email="staff_test@example.com",
            vai_tro="CSKH",
            san_sang_nhan_viec=True,
        )

        # 4. Cau hinh danh muc, Queue va SLA cua M3.
        self.category = TicketCategory.objects.create(
            ten_danh_muc="Hàng bị lỗi",
            mo_ta="San pham Resin bi hu hong",
            dang_hoat_dong=True,
        )

        self.queue = TicketQueue.objects.create(
            ten_queue="CSKH - Sản phẩm",
            mo_ta="Xu ly van de san pham",
            dang_hoat_dong=True,
        )

        self.sla = SLAConfig.objects.create(
            danh_muc=self.category,
            muc_uu_tien="MEDIUM",
            thoi_han_gio=48,
            dang_hoat_dong=True,
        )

        # 5. Tao hai anh JPEG that trong kho M2.
        image_buffer = BytesIO()

        Image.new(
            "RGB",
            (100, 100),
            "white",
        ).save(
            image_buffer,
            format="JPEG",
        )

        image_content = image_buffer.getvalue()

        m2_root = root / "CRM_HULO_m2_private"

        customer_folder = (
            m2_root / f"kh_{self.customer.pk}"
        )
        customer_folder.mkdir(parents=True)

        attachments = []

        for index in (1, 2):
            file_name = f"{uuid4().hex}.jpg"

            source_name = (
                f"kh_{self.customer.pk}/{file_name}"
            )

            source_path = customer_folder / file_name
            source_path.write_bytes(image_content)

            attachments.append({
                "ten_goc": f"anh_san_pham_{index}.jpg",
                "duong_dan_luu": source_name,
                "dung_luong": len(image_content),
            })

        # 6. Tao ban nhap yeu cau M2.
        self.source_request_id = (
            "TEST_M2_M3_RESI_N_001"
        )

        self.draft = {
            "ma_khach_hang": self.customer.pk,
            "source_request_id": self.source_request_id,
            "loai_van_de": "SAN_PHAM_LOI",
            "thong_tin": {
                "tieu_de": "San pham Resin bi hong",
                "mo_ta": (
                    "Khach hang nhan san pham Resin "
                    "bi nut va can duoc ho tro."
                ),
                "ma_don_hang": "ORD_TEST_001",
                "email_lien_he": "hulo_test@example.com",
                "so_dien_thoai": "0900000000",
            },
            "bang_chung": attachments,
        }

    def test_create_ticket_save_images_and_retry(self):
        # LAN 1: Tao Ticket va chuyen hai anh sang M3.
        ticket_1 = tao_ticket_kem_bang_chung(
            yeu_cau=self.draft,
            khach_hang=self.customer,
            danh_muc=self.category,
        )

        ticket_1.refresh_from_db()

        self.assertEqual(
            ticket_1.source_request_id,
            self.source_request_id,
        )

        self.assertEqual(
            ticket_1.khach_hang_id,
            self.customer.pk,
        )

        # SLA phai do M3 thiet lap.
        self.assertEqual(
            ticket_1.sla_config_id,
            self.sla.pk,
        )

        self.assertIsNotNone(
            ticket_1.sla_deadline
        )

        # M3 phai xac dinh Queue san pham.
        self.assertEqual(
            ticket_1.queue_id,
            self.queue.pk,
        )

        # Trang thai phu thuoc quy tac Smart Routing M3.
        self.assertIn(
            ticket_1.trang_thai,
            ("NEW", "ASSIGNED"),
        )

        if ticket_1.trang_thai == "ASSIGNED":
            self.assertIsNotNone(
                ticket_1.nguoi_phu_trach_id
            )
        else:
            self.assertIsNone(
                ticket_1.nguoi_phu_trach_id
            )

        # M3 phai ghi lich su tao Ticket.
        self.assertTrue(
            TicketLog.objects.filter(
                ticket=ticket_1,
                hanh_dong="CREATE",
            ).exists()
        )

        attachments_1 = list(
            TicketAttachment.objects.filter(
                ticket=ticket_1
            ).order_by("pk")
        )

        self.assertEqual(len(attachments_1), 2)

        attachment_ids = {
            item.pk for item in attachments_1
        }

        # Xac nhan file JPEG da luu trong kho M3.
        for item in attachments_1:
            self.assertTrue(
                item.tep_dinh_kem.storage.exists(
                    item.tep_dinh_kem.name
                )
            )

            with item.tep_dinh_kem.open("rb") as file_obj:
                with Image.open(file_obj) as image:
                    self.assertEqual(
                        image.format,
                        "JPEG",
                    )

        # LAN 2: Gui lai cung yeu cau.
        ticket_2 = tao_ticket_kem_bang_chung(
            yeu_cau=self.draft,
            khach_hang=self.customer,
            danh_muc=self.category,
        )

        # Khong tao Ticket moi.
        self.assertEqual(
            ticket_1.pk,
            ticket_2.pk,
        )

        self.assertEqual(
            Ticket.objects.filter(
                source_request_id=self.source_request_id
            ).count(),
            1,
        )

        # Khong tao them anh trung.
        attachments_2 = TicketAttachment.objects.filter(
            ticket=ticket_1
        )

        self.assertEqual(
            attachments_2.count(),
            2,
        )

        self.assertEqual(
            set(
                attachments_2.values_list(
                    "pk",
                    flat=True,
                )
            ),
            attachment_ids,
        )

        # Khong ghi lai su kien CREATE khi gui lai.
        self.assertEqual(
            TicketLog.objects.filter(
                ticket=ticket_1,
                hanh_dong="CREATE",
            ).count(),
            1,
        )

        print(
            "\nM2-M3 INTEGRATION OK"
            f"\nTicket: {ticket_1.ma_ticket}"
            f"\nTrang thai: {ticket_1.trang_thai}"
            f"\nQueue: {ticket_1.queue.ten_queue}"
            f"\nSo anh: {attachments_2.count()}"
        )
