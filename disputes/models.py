from django.db import models
from django.core.validators import MinValueValidator


# =========================================================
# 1. PRODUCT – SẢN PHẨM
# M4 quản lý; các module khác sử dụng lại.
# =========================================================
class Product(models.Model):
    # Khóa chính tự tăng: 1, 2, 3...
    ma_san_pham = models.AutoField(primary_key=True)

    # Mã SKU không được trùng, ví dụ: SP001.
    # Đây là mã nghiệp vụ, khác với khóa chính ở trên.
    ma_sku = models.CharField(
        max_length=50,
        unique=True
    )

    ten_san_pham = models.CharField(
        max_length=255
    )

    # Cách hiển thị sản phẩm trong Admin và danh sách lựa chọn.
    def __str__(self):
        return f"{self.ma_sku} - {self.ten_san_pham}"


# =========================================================
# 2. ORDER – ĐƠN HÀNG
# Mỗi đơn hàng thuộc một Customer do M5 quản lý.
# Một Customer có thể có nhiều đơn hàng.
# =========================================================
class Order(models.Model):
    # Bên trái: giá trị lưu trong database.
    # Bên phải: nội dung hiển thị trên giao diện.
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

    # Khóa chính tự tăng.
    ma_don_hang = models.AutoField(primary_key=True)

    # Mã đơn hàng nghiệp vụ, ví dụ: ORD001.
    so_don_hang = models.CharField(
        max_length=50,
        unique=True
    )

    # Tham chiếu Customer hiện có trong app customers.
    # Không tạo lại model Customer trong app disputes.
    # PROTECT: ngăn xóa khách hàng khi còn đơn hàng liên kết.
    # related_name: cho phép lấy các đơn của khách qua customer.orders.all().
    ma_khach_hang = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders"
    )

    trang_thai = models.CharField(
        max_length=30,
        choices=TRANG_THAI_CHOICES,
        default="CHO_XU_LY"
    )

    # Nhập thời điểm đặt hàng thực tế khi tạo đơn.
    thoi_diem_dat = models.DateTimeField()

    # Các khoản tiền của chi tiết đơn dùng đơn vị tiền tệ này.
    don_vi_tien_te = models.CharField(
        max_length=3,
        choices=TIEN_TE_CHOICES
    )

    def __str__(self):
        return self.so_don_hang


# =========================================================
# 3. ORDERITEM – CHI TIẾT ĐƠN HÀNG
# Một Order có nhiều OrderItem.
# Mỗi OrderItem tham chiếu một Product.
# =========================================================
class OrderItem(models.Model):
    ma_chi_tiet_don = models.AutoField(primary_key=True)

    # Liên kết tới đơn hàng chứa dòng sản phẩm.
    # order.items.all() lấy các dòng chi tiết của một đơn.
    ma_don_hang = models.ForeignKey(
        "disputes.Order",
        on_delete=models.PROTECT,
        related_name="items"
    )

    # Liên kết tới sản phẩm đã mua.
    # PROTECT: không xóa sản phẩm đang được chi tiết đơn tham chiếu.
    ma_san_pham = models.ForeignKey(
        "disputes.Product",
        on_delete=models.PROTECT,
        related_name="order_items"
    )

    # Giữ tên tại thời điểm mua, kể cả khi Product đổi tên sau này.
    ten_san_pham_luc_mua = models.CharField(
        max_length=255
    )

    # Số lượng phải từ 1 trở lên.
    so_luong = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    # TỔNG TIỀN thực trả cho cả dòng, không phải đơn giá.
    # Ví dụ: 2 áo x 200.000 đồng → nhập 400000.
    # DecimalField lưu tiền chính xác với 2 chữ số thập phân.
    gia_tri_da_thanh_toan = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        # Ràng buộc tại database, bổ sung cho kiểm tra của biểu mẫu.
        constraints = [
            models.CheckConstraint(
                condition=models.Q(so_luong__gt=0),
                name="disputes_orderitem_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    gia_tri_da_thanh_toan__gte=0
                ),
                name="disputes_orderitem_paid_nonnegative"
            ),
        ]

    def __str__(self):
        return (
            f"{self.ma_don_hang.so_don_hang} - "
            f"{self.ten_san_pham_luc_mua}"
        )