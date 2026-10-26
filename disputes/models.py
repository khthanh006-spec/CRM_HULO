from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


# =========================================================
# 1. SẢN PHẨM
# =========================================================
class Product(models.Model):
    ma_san_pham = models.AutoField(primary_key=True)
    ma_sku = models.CharField(max_length=50, unique=True)
    ten_san_pham = models.CharField(max_length=255)

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
    so_don_hang = models.CharField(max_length=50, unique=True)

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

    ten_san_pham_luc_mua = models.CharField(max_length=255)

    so_luong = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    # Tổng tiền thực trả của cả dòng sản phẩm.
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
                condition=models.Q(gia_tri_da_thanh_toan__gte=0),
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

    ma_ticket = models.OneToOneField(
        "tickets.Ticket",
        on_delete=models.PROTECT,
        related_name="dispute_case",
        verbose_name="Ticket",
    )

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

        if self.ma_ticket_id and self.ma_don_hang_id:
            if (
                self.ma_ticket.khach_hang_id
                != self.ma_don_hang.ma_khach_hang_id
            ):
                raise ValidationError({
                    "ma_don_hang": (
                        "Đơn hàng không thuộc khách hàng của Ticket này."
                    )
                })

    def __str__(self):
        return f"Hồ sơ #{self.pk} - {self.ma_ticket}"


# =========================================================
# 5. PHƯƠNG ÁN XỬ LÝ
# =========================================================
class CompensationAction(models.Model):
    LOAI_PHUONG_AN_MOI_CHOICES = [
        ("HOAN_TIEN", "Hoàn tiền"),
        ("DOI_HANG", "Đổi hàng"),
        ("GIAO_BO_SUNG", "Giao bổ sung"),
        ("TU_CHOI_HO_TRO", "Từ chối hỗ trợ"),
    ]

    # Chỉ giữ để đọc các phiên bản lịch sử.
    LOAI_PHUONG_AN_CHOICES = LOAI_PHUONG_AN_MOI_CHOICES + [
        ("PHUONG_AN_KHAC", "Phương án khác (dữ liệu cũ)"),
        ("GUI_LAI_HANG", "Gửi lại hàng (dữ liệu cũ)"),
        ("KHONG_BOI_THUONG", "Không bồi thường (dữ liệu cũ)"),
    ]

    TRANG_THAI_CHOICES = [
        ("DE_XUAT", "Đã đề xuất"),
        ("CHO_DUYET", "Chờ phê duyệt"),
        ("TU_CHOI", "Yêu cầu điều chỉnh"),
        ("SAN_SANG_THUC_HIEN", "Sẵn sàng thực hiện"),
        ("DANG_THUC_HIEN", "Đang thực hiện"),
        ("DA_HOAN_TAT", "Đã hoàn tất"),
        ("DA_THAY_THE", "Đã được thay thế"),

        # Giữ các mã cũ, không tự đổi dữ liệu lịch sử.
        ("DA_DUYET", "Đã phê duyệt (dữ liệu cũ)"),
        ("DA_THUC_HIEN", "Đã thực hiện (dữ liệu cũ)"),
    ]

    ma_phuong_an = models.AutoField(primary_key=True)

    ma_ho_so = models.ForeignKey(
        "disputes.DisputeCase",
        on_delete=models.PROTECT,
        related_name="phuong_an_xu_ly",
        verbose_name="Hồ sơ thẩm định",
    )

    phien_ban = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Phiên bản",
    )

    loai_phuong_an = models.CharField(
        max_length=30,
        choices=LOAI_PHUONG_AN_CHOICES,
        verbose_name="Loại phương án",
    )

    noi_dung = models.TextField(
        verbose_name="Nội dung phương án",
    )

    ly_do = models.TextField(
        verbose_name="Căn cứ đề xuất hoặc điều chỉnh",
    )

    so_tien_hoan = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Số tiền đề xuất hoàn",
    )

    don_vi_tien_te = models.CharField(
        max_length=3,
        choices=Order.TIEN_TE_CHOICES,
        verbose_name="Đơn vị tiền tệ",
    )

    # Cho phép trống để giữ các phiên bản cũ.
    # Service sẽ kiểm tra bắt buộc theo từng loại phương án.
    ma_chi_tiet_don = models.ForeignKey(
        "disputes.OrderItem",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cac_phuong_an_xu_ly",
        verbose_name="Sản phẩm trong đơn liên quan",
    )

    so_luong = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name="Số lượng sản phẩm xử lý",
    )

    dia_chi_nhan = models.TextField(
        blank=True,
        verbose_name="Địa chỉ nhận hàng",
    )

    ly_do_tu_choi = models.TextField(
        blank=True,
        verbose_name="Lý do từ chối hỗ trợ",
    )

    ket_qua_thuc_hien = models.TextField(
        blank=True,
        verbose_name="Kết quả và thông tin xác nhận thực hiện",
    )

    thoi_diem_hoan_tat = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Thời điểm hoàn tất",
    )

    nguoi_de_xuat = models.ForeignKey(
        "accounts.Staff",
        on_delete=models.PROTECT,
        related_name="phuong_an_da_de_xuat",
        limit_choices_to={"vai_tro": "ASSESSOR"},
        verbose_name="Nhân viên đề xuất",
    )

    trang_thai = models.CharField(
        max_length=30,
        choices=TRANG_THAI_CHOICES,
        default="DE_XUAT",
        verbose_name="Trạng thái phương án",
    )

    thoi_diem_tao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Thời điểm đề xuất",
    )

    thoi_diem_cap_nhat = models.DateTimeField(
        auto_now=True,
        verbose_name="Thời điểm cập nhật",
    )

    class Meta:
        verbose_name = "Phương án xử lý khiếu nại"
        verbose_name_plural = "Phương án xử lý khiếu nại"
        ordering = ["-phien_ban", "-thoi_diem_tao"]

        constraints = [
            models.UniqueConstraint(
                fields=["ma_ho_so", "phien_ban"],
                name="disputes_action_case_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(phien_ban__gte=1),
                name="disputes_action_version_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        loai_phuong_an="HOAN_TIEN",
                        so_tien_hoan__gt=0,
                    )
                    | models.Q(
                        loai_phuong_an__in=[
                            "DOI_HANG",
                            "GIAO_BO_SUNG",
                            "TU_CHOI_HO_TRO",
                            "PHUONG_AN_KHAC",
                            "GUI_LAI_HANG",
                            "KHONG_BOI_THUONG",
                        ],
                        so_tien_hoan=0,
                    )
                ),
                name="disputes_action_refund_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(so_luong__isnull=True)
                    | models.Q(so_luong__gt=0)
                ),
                name="disputes_action_quantity_positive",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(trang_thai="CHO_DUYET")
                    | models.Q(loai_phuong_an="HOAN_TIEN")
                ),
                name="disputes_action_refund_approval_only",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if not self.noi_dung or not self.noi_dung.strip():
            errors["noi_dung"] = "Bạn cần nhập nội dung phương án."

        if not self.ly_do or not self.ly_do.strip():
            errors["ly_do"] = (
                "Bạn cần nhập căn cứ đề xuất hoặc điều chỉnh."
            )

        if self.loai_phuong_an == "HOAN_TIEN":
            if self.so_tien_hoan is None or self.so_tien_hoan <= 0:
                errors["so_tien_hoan"] = (
                    "Phương án hoàn tiền phải có số tiền lớn hơn 0."
                )
        elif self.loai_phuong_an in dict(self.LOAI_PHUONG_AN_CHOICES):
            if self.so_tien_hoan != 0:
                errors["so_tien_hoan"] = (
                    "Chỉ phương án hoàn tiền được nhập số tiền hoàn."
                )

        if (
            self.trang_thai == "CHO_DUYET"
            and self.loai_phuong_an != "HOAN_TIEN"
        ):
            errors["trang_thai"] = (
                "Chỉ phương án hoàn tiền được chuyển Chờ phê duyệt."
            )

        if self.nguoi_de_xuat_id:
            if self.nguoi_de_xuat.vai_tro != "ASSESSOR":
                errors["nguoi_de_xuat"] = (
                    "Người đề xuất phải là nhân viên thẩm định."
                )

        if self.ma_ho_so_id:
            don_hang = self.ma_ho_so.ma_don_hang

            if don_hang is None:
                errors["ma_ho_so"] = (
                    "Hồ sơ cần được liên kết với đơn hàng."
                )
            else:
                if self.don_vi_tien_te != don_hang.don_vi_tien_te:
                    errors["don_vi_tien_te"] = (
                        "Đơn vị tiền tệ phải trùng với đơn hàng."
                    )

                if self.ma_chi_tiet_don_id:
                    if (
                        self.ma_chi_tiet_don.ma_don_hang_id
                        != don_hang.pk
                    ):
                        errors["ma_chi_tiet_don"] = (
                            "Sản phẩm không thuộc đơn hàng của hồ sơ."
                        )

        if self.ma_chi_tiet_don_id and self.so_luong is not None:
            if self.so_luong > self.ma_chi_tiet_don.so_luong:
                errors["so_luong"] = (
                    "Số lượng xử lý không được vượt số lượng đã mua."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Hồ sơ #{self.ma_ho_so_id} - "
            f"Phương án V{self.phien_ban} - "
            f"{self.get_loai_phuong_an_display()}"
        )


# =========================================================
# 6. KẾT QUẢ PHÊ DUYỆT HOÀN TIỀN
# =========================================================
class ApprovalRecord(models.Model):
    QUYET_DINH_CHOICES = [
        ("PHE_DUYET", "Phê duyệt"),
        ("TU_CHOI", "Từ chối / yêu cầu điều chỉnh"),
    ]

    ma_phe_duyet = models.AutoField(primary_key=True)

    ma_phuong_an = models.OneToOneField(
        "disputes.CompensationAction",
        on_delete=models.PROTECT,
        related_name="ket_qua_phe_duyet",
        verbose_name="Phiên bản phương án",
    )

    nguoi_phe_duyet = models.ForeignKey(
        "accounts.Staff",
        on_delete=models.PROTECT,
        related_name="cac_quyet_dinh_phe_duyet",
        limit_choices_to={"vai_tro": "MANAGER"},
        verbose_name="Quản lý phê duyệt",
    )

    quyet_dinh = models.CharField(
        max_length=20,
        choices=QUYET_DINH_CHOICES,
        verbose_name="Quyết định",
    )

    ly_do = models.TextField(
        blank=True,
        verbose_name="Nhận xét / lý do",
    )

    thoi_diem_phe_duyet = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Thời điểm quyết định",
    )

    class Meta:
        verbose_name = "Kết quả phê duyệt"
        verbose_name_plural = "Kết quả phê duyệt"
        ordering = ["-thoi_diem_phe_duyet"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    quyet_dinh__in=["PHE_DUYET", "TU_CHOI"]
                ),
                name="disputes_approval_decision_valid",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.quyet_dinh == "TU_CHOI":
            if not self.ly_do or not self.ly_do.strip():
                errors["ly_do"] = (
                    "Phải nhập lý do khi yêu cầu điều chỉnh."
                )

        if self.nguoi_phe_duyet_id:
            if self.nguoi_phe_duyet.vai_tro != "MANAGER":
                errors["nguoi_phe_duyet"] = (
                    "Người phê duyệt phải có vai trò Quản lý."
                )

        if self.ma_phuong_an_id:
            if self.ma_phuong_an.loai_phuong_an != "HOAN_TIEN":
                errors["ma_phuong_an"] = (
                    "Chỉ phương án hoàn tiền có quyết định quản lý."
                )

            if (
                self.nguoi_phe_duyet_id
                and self.ma_phuong_an.nguoi_de_xuat_id
                == self.nguoi_phe_duyet_id
            ):
                errors["nguoi_phe_duyet"] = (
                    "Không được tự phê duyệt phương án mình đề xuất."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Phương án #{self.ma_phuong_an_id} - "
            f"{self.get_quyet_dinh_display()}"
        )


from .reconsideration_models import ReconsiderationRecord
