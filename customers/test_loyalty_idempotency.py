
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import (
    Customer,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from .services import change_loyalty_points


class LoyaltyIdempotencyTests(TestCase):

    def setUp(self):
        """
        Tao du lieu rieng cho moi test.
        Khong su dung khach hang trong database that.
        """

        User = get_user_model()

        self.staff_user = User.objects.create_user(
            username="m5_test_staff",
            password="TestPassword123!"
        )

        self.customer_user = User.objects.create_user(
            username="m5_test_customer",
            password="TestPassword123!"
        )

        self.customer = Customer.objects.create(
            ma_tai_khoan=self.customer_user,
            ho_ten="Khach hang kiem thu Loyalty",
            email="m5test@example.com"
        )

        self.account = LoyaltyAccount.objects.create(
            customer=self.customer
        )

    def test_01_earn_same_key_only_once(self):
        """
        Gui hai lan cung yeu cau cong 10 diem.
        Chi duoc cong mot lan.
        """

        key = uuid4()

        first = change_loyalty_points(
            customer=self.customer,
            transaction_type="EARN",
            points=10,
            description="Test cong 10 diem",
            performed_by=self.staff_user,
            idempotency_key=key
        )

        second = change_loyalty_points(
            customer=self.customer,
            transaction_type="EARN",
            points=10,
            description="Test cong 10 diem",
            performed_by=self.staff_user,
            idempotency_key=key
        )

        self.account.refresh_from_db()

        self.assertEqual(first.pk, second.pk)

        self.assertEqual(
            self.account.points_balance,
            10
        )

        self.assertEqual(
            self.account.total_points_earned,
            10
        )

        self.assertEqual(
            LoyaltyTransaction.objects.count(),
            1
        )

        self.assertEqual(
            first.performed_by,
            self.staff_user
        )

    def test_02_redeem_same_key_only_once(self):
        """
        Co 30 diem, doi 10 diem hai lan cung ma.
        So du con 20, khong phai 10.
        """

        change_loyalty_points(
            customer=self.customer,
            transaction_type="EARN",
            points=30,
            description="Tao 30 diem de kiem thu",
            performed_by=self.staff_user,
            idempotency_key=uuid4()
        )

        key = uuid4()

        first = change_loyalty_points(
            customer=self.customer,
            transaction_type="REDEEM",
            points=10,
            description="Test doi 10 diem",
            performed_by=self.staff_user,
            idempotency_key=key
        )

        second = change_loyalty_points(
            customer=self.customer,
            transaction_type="REDEEM",
            points=10,
            description="Test doi 10 diem",
            performed_by=self.staff_user,
            idempotency_key=key
        )

        self.account.refresh_from_db()

        self.assertEqual(first.pk, second.pk)

        self.assertEqual(
            self.account.points_balance,
            20
        )

        self.assertEqual(
            self.account.total_points_earned,
            30
        )

        self.assertEqual(
            LoyaltyTransaction.objects.count(),
            2
        )

    def test_03_same_key_different_content_rejected(self):
        """
        Khong duoc tai su dung ma cu
        cho giao dich co noi dung khac.
        """

        key = uuid4()

        change_loyalty_points(
            customer=self.customer,
            transaction_type="EARN",
            points=5,
            description="Giao dich ban dau",
            performed_by=self.staff_user,
            idempotency_key=key
        )

        with self.assertRaises(ValueError):
            change_loyalty_points(
                customer=self.customer,
                transaction_type="EARN",
                points=50,
                description="Giao dich khac",
                performed_by=self.staff_user,
                idempotency_key=key
            )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.points_balance,
            5
        )

        self.assertEqual(
            LoyaltyTransaction.objects.count(),
            1
        )

    def test_04_redeem_insufficient_points(self):
        """
        Khach hang co 0 diem.
        Khong duoc doi 10 diem.
        """

        with self.assertRaises(ValueError):
            change_loyalty_points(
                customer=self.customer,
                transaction_type="REDEEM",
                points=10,
                description="Test khong du diem",
                performed_by=self.staff_user,
                idempotency_key=uuid4()
            )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.points_balance,
            0
        )

        self.assertEqual(
            LoyaltyTransaction.objects.count(),
            0
        )
