
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Staff
from customers.models import Customer
from tickets.models import Ticket


class TicketDetailAccessTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        # Khach hang so huu Ticket
        customer_user = User.objects.create_user(
            username="test_customer_detail",
            password="TestPass123!",
        )

        cls.customer = Customer.objects.create(
            ma_tai_khoan=customer_user,
            ho_ten="Khach hang test",
            email="customer-detail@example.com",
        )

        # Hai nhan vien CSKH
        cls.staff_user_1 = User.objects.create_user(
            username="test_cskh_detail_1",
            password="TestPass123!",
        )

        cls.staff_1 = Staff.objects.create(
            ma_tai_khoan=cls.staff_user_1,
            ho_ten="Nhan vien CSKH 1",
            vai_tro="CSKH",
        )

        cls.staff_user_2 = User.objects.create_user(
            username="test_cskh_detail_2",
            password="TestPass123!",
        )

        cls.staff_2 = Staff.objects.create(
            ma_tai_khoan=cls.staff_user_2,
            ho_ten="Nhan vien CSKH 2",
            vai_tro="CSKH",
        )

        # Tai khoan quan ly
        cls.manager_user = User.objects.create_user(
            username="test_manager_detail",
            password="TestPass123!",
        )

        Staff.objects.create(
            ma_tai_khoan=cls.manager_user,
            ho_ten="Quan ly test",
            vai_tro="MANAGER",
        )

        # Ticket NEW chua phan cong
        cls.ticket_new = Ticket.objects.create(
            ma_ticket="TK_TEST_DETAIL_NEW",
            khach_hang=cls.customer,
            tieu_de="Ticket moi",
            noi_dung="Yeu cau moi chua phan cong",
            muc_uu_tien="MEDIUM",
            trang_thai="NEW",
            nguoi_phu_trach=None,
        )

        # Ticket da giao cho CSKH 1
        cls.ticket_assigned = Ticket.objects.create(
            ma_ticket="TK_TEST_DETAIL_ASSIGNED",
            khach_hang=cls.customer,
            tieu_de="Ticket da phan cong",
            noi_dung="Yeu cau da giao cho CSKH 1",
            muc_uu_tien="MEDIUM",
            trang_thai="ASSIGNED",
            nguoi_phu_trach=cls.staff_1,
        )

    def detail_url(self, ticket):
        return reverse(
            "tickets:detail",
            kwargs={"pk": ticket.pk},
        )

    def test_cskh_can_view_new_unassigned_ticket(self):
        self.client.force_login(self.staff_user_1)

        response = self.client.get(
            self.detail_url(self.ticket_new)
        )

        self.assertEqual(response.status_code, 200)

    def test_cskh_can_view_own_assigned_ticket(self):
        self.client.force_login(self.staff_user_1)

        response = self.client.get(
            self.detail_url(self.ticket_assigned)
        )

        self.assertEqual(response.status_code, 200)

    def test_cskh_cannot_view_other_staff_ticket(self):
        self.client.force_login(self.staff_user_2)

        response = self.client.get(
            self.detail_url(self.ticket_assigned)
        )

        self.assertEqual(response.status_code, 403)

    def test_manager_can_view_ticket(self):
        self.client.force_login(self.manager_user)

        response = self.client.get(
            self.detail_url(self.ticket_assigned)
        )

        self.assertEqual(response.status_code, 200)
