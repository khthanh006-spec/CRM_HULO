from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


# =========================================================
# 1. SẢN PHẨM
# =========================================================
class Product(models.Model):
    ma_san_pham = models.AutoField(primary_key=True)

    ma_sku = models.CharField(
        max_length=50,
        unique=True,
    )

    ten_san_pham = models.CharField(
        max_length=255,
    )

    def __str__(self):
        return f"{self.ma_sku} - {self.ten_san_pham}"


# =========================================================
# 2. ĐƠN HÀNG
# =========================================================
class Order(models.Model):
    TRANG_THAI_CHOICES = [
        ("CHO_XU_LY", "Chờ xử lý"),
        ("DANG_GIAO", "Đang giao"),
        ("DA_GIAO", "Đã giao"),
        ("DA_HUY", "Đã hủy"),
    ]

    TIEN_TE_CHOICES = [
        ("VND", "VND"),
        ("USD", "USD"),
        ("GBP", "GBP"),
        ("EUR", "EUR"),
    ]

    ma_don_hang = models.AutoField(primary_key=True)

    so_don_hang = models.CharField(
        max_length=50,
        unique=True,
    )

    ma_khach_hang = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
    )

    trang_thai = models.CharField(
        max_length=30,
        choices=TRANG_THAI_CHOICES,
        default="CHO_XU_LY",
    )

    thoi_diem_dat = models.DateTimeField()

    don_vi_tien_te = models.CharField(
        max_length=3,
        choices=TIEN_TE_CHOICES,
    )

    def __str__(self):
        return self.so_don_hang


# =========================================================
# 3. CHI TIẾT ĐƠN HÀNG
# =========================================================
class OrderItem(models.Model):
    ma_chi_tiet_don = models.AutoField(primary_key=True)

    ma_don_hang = models.ForeignKey(
        "disputes.Order",
        on_delete=models.PROTECT,
        related_name="items",
    )

    ma_san_pham = models.ForeignKey(
        "disputes.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    # Giữ tên sản phẩm tại thời điểm mua.
    ten_san_pham_luc_mua = models.CharField(
        max_length=255,
    )

    so_luong = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    # Tổng tiền thực trả của cả dòng sản phẩm, không phải đơn giá.
    gia_tri_da_thanh_toan = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(so_luong__gt=0),
                name="disputes_orderitem_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    gia_tri_da_thanh_toan__gte=0
                ),
                name="disputes_orderitem_paid_nonnegative",
            ),
        ]

    def __str__(self):
        return (
            f"{self.ma_don_hang.so_don_hang} - "
            f"{self.ten_san_pham_luc_mua}"
        )


# =========================================================
# 4. HỒ SƠ THẨM ĐỊNH
# =========================================================
class DisputeCase(models.Model):
    TRANG_THAI_CHOICES = [
        ("CHO_TIEP_NHAN", "Chờ tiếp nhận"),
        ("DANG_THAM_DINH", "Đang thẩm định"),
        ("CHO_BO_SUNG", "Chờ bổ sung bằng chứng"),
        ("DA_KET_LUAN", "Đã kết luận"),
    ]

    ma_ho_so = models.AutoField(primary_key=True)

    # Một Ticket có tối đa một hồ sơ thẩm định.
    ma_ticket = models.OneToOneField(
        "tickets.Ticket",
        on_delete=models.PROTECT,
        related_name="dispute_case",
        verbose_name="Ticket",
    )

    # Đơn hàng cụ thể đang bị khiếu nại.
    # Cho phép trống để giữ được các hồ sơ đã tạo trước đây.
    ma_don_hang = models.ForeignKey(
        "disputes.Order",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ho_so_khieu_nai",
        verbose_name="Đơn hàng bị khiếu nại",
    )

    ma_nhan_vien_tham_dinh = models.ForeignKey(
        "accounts.Staff",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ho_so_tham_dinh",
        limit_choices_to={"vai_tro": "ASSESSOR"},
        verbose_name="Nhân viên thẩm định",
    )

    trang_thai = models.CharField(
        max_length=30,
        choices=TRANG_THAI_CHOICES,
        default="CHO_TIEP_NHAN",
        verbose_name="Trạng thái hồ sơ",
    )

    ket_luan = models.TextField(
        blank=True,
        verbose_name="Kết luận thẩm định",
    )

    thoi_diem_tao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Thời điểm tạo",
    )

    thoi_diem_cap_nhat = models.DateTimeField(
        auto_now=True,
        verbose_name="Thời điểm cập nhật",
    )

    class Meta:
        verbose_name = "Hồ sơ thẩm định"
        verbose_name_plural = "Hồ sơ thẩm định"
        ordering = ["-thoi_diem_tao"]

    def clean(self):
        super().clean()

        # Đơn hàng phải thuộc đúng khách hàng của Ticket.
        if self.ma_ticket_id and self.ma_don_hang_id:
            if (
                self.ma_ticket.khach_hang_id
                != self.ma_don_hang.ma_khach_hang_id
            ):
                raise ValidationError(
                    {
                        "ma_don_hang": (
                            "Đơn hàng không thuộc khách hàng "
                            "của Ticket này."
                        )
                    }
                )

    def __str__(self):
        return f"Hồ sơ #{self.pk} - {self.ma_ticket}"