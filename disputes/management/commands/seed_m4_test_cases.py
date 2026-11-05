
"""Tạo 8 tình huống kiểm thử M4, không sửa dữ liệu có sẵn.

Chạy: python manage.py seed_m4_test_cases
"""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Staff
from customers.models import Customer
from disputes.models import DisputeCase, Order, OrderItem, Product
from disputes.services import tao_hoac_lay_ho_so
from tickets.models import Ticket


CASES = (
    (
        "001",
        "Sản phẩm bị hỏng khi nhận",
        "Sổ tay bìa cứng A5",
        "SO-A5",
        2,
        "180000",
        "DA_GIAO",
        "Nhận sổ tay bị rách bìa, yêu cầu thẩm định và xử lý.",
    ),
    (
        "002",
        "Giao sai sản phẩm",
        "Bút gel xanh 0.5mm",
        "BUT-GEL",
        5,
        "75000",
        "DA_GIAO",
        "Đặt bút gel xanh nhưng nhận bút màu đen, yêu cầu đổi hàng.",
    ),
    (
        "003",
        "Đơn báo đã giao nhưng chưa nhận",
        "Bộ giấy ghi chú",
        "GIAY-NOTE",
        3,
        "90000",
        "DA_GIAO",
        "Hệ thống ghi nhận giao thành công nhưng khách chưa nhận được hàng.",
    ),
    (
        "004",
        "Yêu cầu hoàn tiền vượt giá trị đơn",
        "Thước kẻ 20cm",
        "THUOC-20",
        1,
        "25000",
        "DA_GIAO",
        "Khách yêu cầu hoàn 100.000 VND dù tổng giá trị sản phẩm "
        "là 25.000 VND; kiểm tra chặn vượt hạn mức.",
    ),
    (
        "005",
        "Khách không đồng ý kết luận",
        "Hộp bút vải",
        "HOP-BUT",
        1,
        "120000",
        "DA_GIAO",
        "Tình huống kiểm thử quy trình khách không đồng ý "
        "và xem xét lại kết luận.",
    ),
    (
        "006",
        "Hoàn tiền cần quản lý phê duyệt",
        "Sổ planner",
        "PLANNER",
        2,
        "240000",
        "DA_GIAO",
        "Khách yêu cầu hoàn 120.000 VND; kiểm thử gửi phê duyệt "
        "và quản lý xét duyệt.",
    ),
    (
        "007",
        "Hồ sơ thiếu bằng chứng",
        "Bút highlight",
        "HIGHLIGHT",
        4,
        "80000",
        "DA_GIAO",
        "Khách phản ánh sản phẩm lỗi nhưng chưa gửi hình ảnh "
        "hoặc video chứng minh.",
    ),
    (
        "008",
        "Thiếu sản phẩm trong kiện hàng",
        "Kẹp giấy màu",
        "KEP-GIAY",
        6,
        "60000",
        "DA_GIAO",
        "Đơn hàng thiếu 2 sản phẩm; kiểm thử phương án giao bổ sung.",
    ),
)


class Command(BaseCommand):
    help = (
        "Tạo 8 Ticket + đơn hàng + hồ sơ M4TEST để kiểm thử "
        "trên giao diện. Chạy lại không tạo trùng."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        assessor = (
            Staff.objects.select_related("ma_tai_khoan")
            .filter(
                ma_tai_khoan__username="thamdinh01",
                vai_tro="ASSESSOR",
                san_sang_nhan_viec=True,
                ma_tai_khoan__is_active=True,
            )
            .first()
        )

        cskh = (
            Staff.objects.filter(
                ma_tai_khoan__username="cskh01",
                vai_tro="CSKH",
            )
            .first()
        )

        if not assessor or not cskh:
            raise CommandError(
                "Cần cskh01 (CSKH) và thamdinh01 "
                "(ASSESSOR, sẵn sàng, active)."
            )

        customers = list(
            Customer.objects.order_by("pk")[:len(CASES)]
        )

        if len(customers) < len(CASES):
            raise CommandError(
                "Cần ít nhất 8 khách hàng hiện có."
            )

        created = 0

        for (
            suffix,
            title,
            product_name,
            sku_suffix,
            qty,
            amount,
            status,
            description,
        ), customer in zip(CASES, customers):

            code = f"M4TEST-{suffix}"
            order_code = f"M4TEST-ORDER-{suffix}"
            sku = f"M4TEST-{sku_suffix}"

            product, _ = Product.objects.get_or_create(
                ma_sku=sku,
                defaults={
                    "ten_san_pham": product_name,
                },
            )

            order, _ = Order.objects.get_or_create(
                so_don_hang=order_code,
                defaults={
                    "ma_khach_hang": customer,
                    "trang_thai": status,
                    "thoi_diem_dat": timezone.now(),
                    "don_vi_tien_te": "VND",
                },
            )

            if order.ma_khach_hang_id != customer.pk:
                raise CommandError(
                    f"{order_code} đã tồn tại nhưng "
                    "thuộc khách hàng khác."
                )

            if not OrderItem.objects.filter(
                ma_don_hang=order
            ).exists():

                item = OrderItem(
                    ma_don_hang=order,
                    ma_san_pham=product,
                    ten_san_pham_luc_mua=product_name,
                    so_luong=qty,
                    gia_tri_da_thanh_toan=Decimal(amount),
                )

                item.full_clean()
                item.save()

            ticket = Ticket.objects.filter(
                ma_ticket=code
            ).first()

            if ticket is None:
                ticket = Ticket(
                    ma_ticket=code,
                    khach_hang=customer,
                    tieu_de=f"[M4TEST-{suffix}] {title}",
                    noi_dung=(
                        f"{description}\n"
                        f"Mã đơn hàng: {order_code}"
                    ),
                    trang_thai="IN_PROGRESS",
                    trang_thai_tham_dinh="WAITING",
                    nguoi_phu_trach=cskh,
                    thoi_diem_yeu_cau_tham_dinh=timezone.now(),
                )

                ticket.full_clean()
                ticket.save()

                created += 1

            elif ticket.khach_hang_id != customer.pk:
                raise CommandError(
                    f"{code} đã tồn tại nhưng "
                    "thuộc khách hàng khác."
                )

            elif (
                ticket.trang_thai != "IN_PROGRESS"
                or ticket.trang_thai_tham_dinh != "WAITING"
            ):
                self.stdout.write(
                    self.style.WARNING(
                        f"{code}: Ticket đã chuyển trạng thái; "
                        "giữ nguyên, bỏ qua tạo hồ sơ."
                    )
                )
                continue

            existing = DisputeCase.objects.filter(
                ma_ticket=ticket
            ).first()

            if (
                existing
                and existing.ma_don_hang_id
                not in (None, order.pk)
            ):
                raise CommandError(
                    f"{code} đã gắn đơn hàng khác; "
                    "không thay đổi."
                )

            dispute = tao_hoac_lay_ho_so(
                ticket=ticket,
                ma_don_hang=order,
            )

            self.stdout.write(
                f"{code} | order={order.so_don_hang} "
                f"| dispute=#{dispute.pk} "
                f"| {dispute.trang_thai} "
                f"| assessor={dispute.ma_nhan_vien_tham_dinh_id}"
            )

        total = DisputeCase.objects.filter(
            ma_ticket__ma_ticket__startswith="M4TEST-"
        ).count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Hoàn tất: tạo mới {created} Ticket; "
                f"tổng hồ sơ M4TEST hiện có: {total}."
            )
        )
