
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone


class OrphanCleanupTest(TestCase):

    def test_orphan_file_is_quarantined(self):
        with TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir) / "media"
            media_root.mkdir()

            orphan_folder = (
                media_root / "ticket_attachments" / "2026" / "10" / "01"
            )
            orphan_folder.mkdir(parents=True)

            orphan_file = orphan_folder / "orphan.jpg"
            orphan_file.write_bytes(b"test-orphan-content")

            quarantine_root = (
                media_root.parent / "CRM_HULO_m3_quarantine"
            )

            # Gia lap file da cu hon 24 gio.
            old_time = timezone.now().timestamp() - 48 * 3600

            import os
            os.utime(orphan_file, (old_time, old_time))

            output = StringIO()

            with override_settings(MEDIA_ROOT=media_root):
                call_command(
                    "kiem_tra_anh_mo_coi",
                    "--hours",
                    "24",
                    "--quarantine",
                    stdout=output,
                )

            self.assertFalse(orphan_file.exists())

            quarantined_files = list(
                quarantine_root.glob("*orphan.jpg")
            )

            self.assertEqual(len(quarantined_files), 1)
            self.assertEqual(
                quarantined_files[0].read_bytes(),
                b"test-orphan-content",
            )

            self.assertIn(
                "Da cach ly 1 file",
                output.getvalue(),
            )


    def test_valid_attachment_is_not_quarantined(self):
        import os
        from django.contrib.auth import get_user_model
        from django.core.files.base import ContentFile

        from customers.models import Customer
        from tickets.models import Ticket, TicketAttachment

        with TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir) / "media"
            media_root.mkdir()

            with override_settings(MEDIA_ROOT=media_root):
                User = get_user_model()

                user = User.objects.create_user(
                    username="test_orphan_valid_customer",
                    password="TestPass123!",
                )

                customer = Customer.objects.create(
                    ma_tai_khoan=user,
                    ho_ten="Khach hang kiem thu",
                    email="orphan-valid@example.com",
                )

                ticket = Ticket.objects.create(
                    ma_ticket="TK_TEST_ORPHAN_VALID",
                    khach_hang=customer,
                    tieu_de="Kiem tra bao ve anh hop le",
                    noi_dung="Anh da duoc Ticket tham chieu.",
                    muc_uu_tien="MEDIUM",
                    trang_thai="IN_PROGRESS",
                )

                attachment = TicketAttachment(
                    ticket=ticket,
                    ten_tep_goc="anh_hop_le.jpg",
                    nguoi_tai_len=user,
                )

                attachment.tep_dinh_kem.save(
                    "anh_hop_le.jpg",
                    ContentFile(b"test-valid-content"),
                    save=True,
                )

                saved_path = Path(
                    attachment.tep_dinh_kem.path
                )

                # Gia lap anh da luu hon 48 gio.
                old_time = (
                    timezone.now().timestamp() - 48 * 3600
                )
                os.utime(saved_path, (old_time, old_time))

                output = StringIO()

                call_command(
                    "kiem_tra_anh_mo_coi",
                    "--hours",
                    "24",
                    "--quarantine",
                    stdout=output,
                )

                # Anh hop le van phai ton tai.
                self.assertTrue(saved_path.exists())

                # Ban ghi database van con nguyen.
                self.assertTrue(
                    TicketAttachment.objects.filter(
                        pk=attachment.pk
                    ).exists()
                )

                # Khong duoc cach ly anh hop le.
                self.assertIn(
                    "Da cach ly 0 file",
                    output.getvalue(),
                )

