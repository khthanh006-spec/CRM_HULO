
from unittest.mock import patch, Mock

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseForbidden
from django.test import SimpleTestCase, RequestFactory
from django.urls import reverse

from tickets.attachment_views import (
    ticket_attachment_download,
)


class AttachmentAccessTest(SimpleTestCase):

    def test_guest_must_login(self):
        url = reverse(
            "tickets:attachment_download",
            kwargs={"pk": 999999},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_logged_in_user_without_permission_is_forbidden(self):
        """
        Nguoi da dang nhap nhung khong so huu Ticket
        va khong co quyen nhan vien phai bi chan.
        """

        request = RequestFactory().get(
            "/tickets/attachments/1/download/"
        )

        user = Mock()
        user.is_authenticated = True
        user.is_superuser = False
        user.staff_profile = None

        request.user = user

        ticket = Mock()
        ticket.khach_hang_id = 100
        ticket.nguoi_phu_trach_id = None
        ticket.trang_thai = "IN_PROGRESS"

        bang_chung = Mock()
        bang_chung.ticket = ticket

        with patch(
            "tickets.attachment_views.get_object_or_404",
            return_value=bang_chung,
        ):
            with patch(
                "tickets.attachment_views.Customer.objects.filter"
            ) as mock_filter:
                mock_filter.return_value.exists.return_value = False

                response = ticket_attachment_download(
                    request,
                    pk=1,
                )

        self.assertEqual(
            response.status_code,
            403,
        )


from tempfile import TemporaryDirectory
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from accounts.models import Staff
from customers.models import Customer
from tickets.models import Ticket, TicketAttachment


class AttachmentDatabaseAccessTest(TestCase):

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.settings_override = override_settings(
            MEDIA_ROOT=self.temp_dir.name
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        User = get_user_model()

        self.user_a = User.objects.create_user(
            username="test_customer_a",
            password="TestPass123!",
        )
        self.user_b = User.objects.create_user(
            username="test_customer_b",
            password="TestPass123!",
        )

        self.customer_a = Customer.objects.create(
            ma_tai_khoan=self.user_a,
            ho_ten="Khach hang A",
            email="customer_a@example.com",
        )
        self.customer_b = Customer.objects.create(
            ma_tai_khoan=self.user_b,
            ho_ten="Khach hang B",
            email="customer_b@example.com",
        )

        self.staff_user_1 = User.objects.create_user(
            username="test_cskh_1",
            password="TestPass123!",
        )
        self.staff_user_2 = User.objects.create_user(
            username="test_cskh_2",
            password="TestPass123!",
        )

        self.staff_1 = Staff.objects.create(
            ma_tai_khoan=self.staff_user_1,
            ho_ten="Nhan vien 1",
            vai_tro="CSKH",
        )
        self.staff_2 = Staff.objects.create(
            ma_tai_khoan=self.staff_user_2,
            ho_ten="Nhan vien 2",
            vai_tro="CSKH",
        )

        self.ticket = Ticket.objects.create(
            ma_ticket="TK_TEST_ATTACHMENT_ACCESS",
            khach_hang=self.customer_a,
            tieu_de="Kiem thu quyen xem anh",
            noi_dung="San pham bi hu hong",
            muc_uu_tien="MEDIUM",
            trang_thai="IN_PROGRESS",
            nguoi_phu_trach=self.staff_1,
        )

        self.attachment = TicketAttachment(
            ticket=self.ticket,
            ten_tep_goc="bang_chung.jpg",
            nguoi_tai_len=self.user_a,
        )

        self.attachment.tep_dinh_kem.save(
            "test_access.jpg",
            ContentFile(b"test-image-content"),
            save=True,
        )

        self.url = reverse(
            "tickets:attachment_download",
            kwargs={"pk": self.attachment.pk},
        )

    def test_owner_can_download(self):
        self.client.force_login(self.user_a)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        response.close()

    def test_other_customer_cannot_download(self):
        self.client.force_login(self.user_b)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_assigned_staff_can_download(self):
        self.client.force_login(self.staff_user_1)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        response.close()

    def test_unassigned_staff_cannot_download(self):
        self.client.force_login(self.staff_user_2)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_manager_can_download(self):
        manager_user = get_user_model().objects.create_user(
            username="test_manager_attachment",
            password="TestPass123!",
        )

        Staff.objects.create(
            ma_tai_khoan=manager_user,
            ho_ten="Quan ly kiem thu",
            vai_tro="MANAGER",
        )

        self.client.force_login(manager_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        response.close()

    def test_assessor_has_no_automatic_access(self):
        assessor_user = get_user_model().objects.create_user(
            username="test_assessor_attachment",
            password="TestPass123!",
        )

        Staff.objects.create(
            ma_tai_khoan=assessor_user,
            ho_ten="Nhan vien tham dinh",
            vai_tro="ASSESSOR",
        )

        self.client.force_login(assessor_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
