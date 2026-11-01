from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import Staff
from customers.models import Customer
from tickets.models import Ticket

from .execution_services import cap_nhat_thuc_hien
from .models import (
    ApprovalRecord,
    CompensationAction,
    DisputeCase,
    Order,
    OrderItem,
    Product,
)
from .plan_services import luu_phuong_an_theo_bpmn


class RefundLimitTests(TestCase):
    """
    Kiểm thử giới hạn hoàn tiền của Module 4.

    Django tạo cơ sở dữ liệu kiểm thử riêng và tự tạo các dữ liệu
    bên dưới. Không dùng hồ sơ demo trong cơ sở dữ liệu đang chạy.
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.customer_user = User.objects.create_user(
            username="test_customer",
            password="test-password",
        )

        cls.assessor_user = User.objects.create_user(
            username="test_assessor",
            password="test-password",
        )

        cls.manager_user = User.objects.create_user(
            username="test_manager",
            password="test-password",
        )

        cls.customer = Customer.objects.create(
            ma_tai_khoan=cls.customer_user,
            ho_ten="Khach hang kiem thu",
            email="customer-test@example.com",
        )

        cls.assessor = Staff.objects.create(
            ma_tai_khoan=cls.assessor_user,
            ho_ten="Nhan vien tham dinh kiem thu",
            email="assessor-test@example.com",
            vai_tro="ASSESSOR",
        )

        cls.manager = Staff.objects.create(
            ma_tai_khoan=cls.manager_user,
            ho_ten="Quan ly kiem thu",
            email="manager-test@example.com",
            vai_tro="MANAGER",
        )

        cls.product = Product.objects.create(
            ma_sku="TEST-REFUND-001",
            ten_san_pham="San pham kiem thu",
        )

        cls.order = Order.objects.create(
            so_don_hang="TEST-ORDER-001",
            ma_khach_hang=cls.customer,
            trang_thai="DA_GIAO",
            thoi_diem_dat=timezone.now(),
            don_vi_tien_te="VND",
        )

        cls.item = OrderItem.objects.create(
            ma_don_hang=cls.order,
            ma_san_pham=cls.product,
            ten_san_pham_luc_mua="San pham kiem thu",
            so_luong=1,
            gia_tri_da_thanh_toan=Decimal("500000.00"),
        )

    def tao_ho_so(self, so_thu_tu):
        ticket = Ticket.objects.create(
            ma_ticket=f"TEST-REFUND-{so_thu_tu}",
            khach_hang=self.customer,
            tieu_de="Kiem thu hoan tien",
            noi_dung="Noi dung khieu nai phuc vu kiem thu.",
            trang_thai="IN_PROGRESS",
            trang_thai_tham_dinh="WAITING",
        )

        return DisputeCase.objects.create(
            ma_ticket=ticket,
            ma_don_hang=self.order,
            ma_nhan_vien_tham_dinh=self.assessor,
            trang_thai="DA_KET_LUAN",
            ket_luan="Ket luan tham dinh phuc vu kiem thu.",
        )

    def lap_phuong_an(self, ho_so):
        return luu_phuong_an_theo_bpmn(
            user=self.assessor_user,
            ma_ho_so=ho_so.pk,
            loai_phuong_an="HOAN_TIEN",
            noi_dung="De xuat hoan tien cho san pham.",
            ly_do="San pham khong dat yeu cau.",
            so_tien_hoan=Decimal("500000.00"),
            phien_ban_hien_tai=0,
            ma_chi_tiet_don=self.item.pk,
            so_luong=1,
        )

    def phe_duyet(self, phuong_an):
        ApprovalRecord.objects.create(
            ma_phuong_an=phuong_an,
            nguoi_phe_duyet=self.manager,
            quyet_dinh="PHE_DUYET",
            ly_do="Phe duyet de kiem thu.",
        )

        phuong_an.trang_thai = "SAN_SANG_THUC_HIEN"
        phuong_an.save(
            update_fields=["trang_thai", "thoi_diem_cap_nhat"]
        )

    def test_chan_hai_de_xuat_hoan_vuot_gia_tri_dong_hang(self):
        ho_so_1 = self.tao_ho_so(1)
        ho_so_2 = self.tao_ho_so(2)

        phuong_an_1 = self.lap_phuong_an(ho_so_1)

        self.assertEqual(phuong_an_1.trang_thai, "CHO_DUYET")

        with self.assertRaises(ValidationError) as loi:
            self.lap_phuong_an(ho_so_2)

        self.assertIn(
            "vượt phần còn được hoàn",
            " ".join(loi.exception.messages),
        )

        self.assertEqual(
            CompensationAction.objects.filter(
                ma_ho_so=ho_so_2
            ).count(),
            0,
        )

    def test_hoan_tat_hop_le_va_chan_hoan_them_vuot_gioi_han(self):
        ho_so_1 = self.tao_ho_so(1)
        phuong_an_1 = self.lap_phuong_an(ho_so_1)
        self.phe_duyet(phuong_an_1)

        ket_qua = cap_nhat_thuc_hien(
            user=self.assessor_user,
            ma_ho_so=ho_so_1.pk,
            ma_phuong_an=phuong_an_1.pk,
            ket_qua_thuc_hien="Da hoan tien phuc vu kiem thu.",
            hoan_tat=True,
        )

        ho_so_1.ma_ticket.refresh_from_db()

        self.assertEqual(ket_qua.trang_thai, "DA_HOAN_TAT")
        self.assertEqual(
            ho_so_1.ma_ticket.trang_thai_tham_dinh,
            "COMPLETED",
        )

        # Giả lập dữ liệu phương án cũ đã tồn tại trước khi
        # bổ sung chức năng kiểm tra giới hạn lúc lập phương án.
        ho_so_2 = self.tao_ho_so(2)

        phuong_an_2 = CompensationAction.objects.create(
            ma_ho_so=ho_so_2,
            phien_ban=1,
            loai_phuong_an="HOAN_TIEN",
            noi_dung="Phuong an cu can doi soat.",
            ly_do="Du lieu phuc vu kiem thu.",
            so_tien_hoan=Decimal("500000.00"),
            don_vi_tien_te="VND",
            ma_chi_tiet_don=self.item,
            so_luong=1,
            nguoi_de_xuat=self.assessor,
            trang_thai="SAN_SANG_THUC_HIEN",
        )

        self.phe_duyet(phuong_an_2)

        with self.assertRaises(ValidationError) as loi:
            cap_nhat_thuc_hien(
                user=self.assessor_user,
                ma_ho_so=ho_so_2.pk,
                ma_phuong_an=phuong_an_2.pk,
                ket_qua_thuc_hien="Da hoan tien phuc vu kiem thu.",
                hoan_tat=True,
            )

        self.assertIn(
            "vượt phần còn được hoàn",
            " ".join(loi.exception.messages),
        )

        phuong_an_2.refresh_from_db()
        ho_so_2.ma_ticket.refresh_from_db()

        self.assertEqual(
            phuong_an_2.trang_thai,
            "SAN_SANG_THUC_HIEN",
        )
        self.assertEqual(
            ho_so_2.ma_ticket.trang_thai_tham_dinh,
            "WAITING",
        )