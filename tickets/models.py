
from django.db import models
from django.conf import settings


# 1. DANH MỤC VẤN ĐỀ
class TicketCategory(models.Model):
    ten_danh_muc = models.CharField(max_length=100, unique=True)
    mo_ta = models.TextField(blank=True)
    dang_hoat_dong = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Ticket category"
        verbose_name_plural = "Ticket categories"

    def __str__(self):
        return self.ten_danh_muc


# 2. HÀNG ĐỢI TICKET
class TicketQueue(models.Model):
    ten_queue = models.CharField(max_length=100, unique=True)
    mo_ta = models.TextField(blank=True)
    dang_hoat_dong = models.BooleanField(default=True)

    def __str__(self):
        return self.ten_queue


# 3. CẤU HÌNH SLA
class SLAConfig(models.Model):
    PRIORITY_CHOICES = [
        ('LOW', 'Thấp'),
        ('MEDIUM', 'Trung bình'),
        ('HIGH', 'Cao'),
        ('URGENT', 'Khẩn cấp'),
    ]

    danh_muc = models.ForeignKey(
        TicketCategory,
        on_delete=models.PROTECT,
        related_name='sla_configs'
    )

    muc_uu_tien = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES
    )

    thoi_han_gio = models.PositiveIntegerField()
    dang_hoat_dong = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['danh_muc', 'muc_uu_tien'],
                name='unique_category_priority_sla'
            )
        ]

    def __str__(self):
        return (
            f"{self.danh_muc} - "
            f"{self.get_muc_uu_tien_display()} - "
            f"{self.thoi_han_gio} giờ"
        )


# 4. TICKET CHÍNH
class Ticket(models.Model):

    # ==========================================
    # UC-3.5 - XÁC NHẬN KẾT QUẢ CỦA KHÁCH HÀNG
    # ==========================================

    CONFIRMATION_CHOICES = [
        ('PENDING', 'Chờ xác nhận'),
        ('AGREED', 'Đã đồng ý'),
        ('DISAGREED', 'Không đồng ý'),
    ]

    trang_thai_xac_nhan = models.CharField(
        max_length=20,
        choices=CONFIRMATION_CHOICES,
        default='PENDING'
    )

    ly_do_khong_dong_y = models.TextField(
        blank=True
    )

    thoi_diem_xac_nhan = models.DateTimeField(
        null=True,
        blank=True
    )


    PRIORITY_CHOICES = SLAConfig.PRIORITY_CHOICES

    STATUS_CHOICES = [
        ('NEW', 'Mới tạo'),
        ('ASSIGNED', 'Đã phân công'),
        ('IN_PROGRESS', 'Đang xử lý'),
        ('RESOLVED', 'Đã giải quyết'),
        ('CLOSED', 'Đã đóng'),
        ('REOPENED', 'Mở lại'),
    ]

    ma_ticket = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True
    )


    # Mã yêu cầu nguồn từ M1 hoặc M2
    # Dùng để chống tạo Ticket trùng khi gửi lại
    source_request_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True
    )


    khach_hang = models.ForeignKey(
        'customers.Customer',
        on_delete=models.PROTECT,
        related_name='tickets'
    )

    tieu_de = models.CharField(max_length=255)
    noi_dung = models.TextField()

    danh_muc = models.ForeignKey(
        TicketCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    muc_uu_tien = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        null=True,
        blank=True
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW'
    )

    queue = models.ForeignKey(
        TicketQueue,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    nguoi_phu_trach = models.ForeignKey(
        'accounts.Staff',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='tickets_duoc_giao'
    )

    sla_config = models.ForeignKey(
        SLAConfig,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    sla_deadline = models.DateTimeField(
        null=True,
        blank=True
    )


    ket_qua_xu_ly = models.TextField(blank=True)

    # UC3.4 - Theo dõi yêu cầu thẩm định trong M3
    ASSESSMENT_STATUS_CHOICES = [
        ('NOT_REQUESTED', 'Chưa yêu cầu'),
        ('WAITING', 'Đang chờ kết quả'),
        ('COMPLETED', 'Đã có kết quả'),
    ]

    trang_thai_tham_dinh = models.CharField(
        max_length=20,
        choices=ASSESSMENT_STATUS_CHOICES,
        default='NOT_REQUESTED'
    )

    thoi_diem_yeu_cau_tham_dinh = models.DateTimeField(
        null=True,
        blank=True
    )

    thoi_diem_tao = models.DateTimeField(auto_now_add=True)
    thoi_diem_cap_nhat = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.ma_ticket or f"Ticket #{self.pk}"


# 5. LỊCH SỬ XỬ LÝ TICKET
class TicketLog(models.Model):

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='logs'
    )

    nguoi_thuc_hien = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    hanh_dong = models.CharField(max_length=100)

    noi_dung = models.TextField(blank=True)

    thoi_diem = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ticket} - {self.hanh_dong}"


# 6. PHẢN HỒI VÀ GHI CHÚ
class TicketMessage(models.Model):

    MESSAGE_TYPE_CHOICES = [
        ('PUBLIC', 'Phản hồi công khai'),
        ('INTERNAL', 'Ghi chú nội bộ'),
    ]

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='messages'
    )

    nguoi_gui = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )

    loai_tin_nhan = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES
    )

    noi_dung = models.TextField()

    thoi_diem_gui = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.ticket} - "
            f"{self.get_loai_tin_nhan_display()}"
        )


# 7. TỆP ĐÍNH KÈM CỦA TICKET
class TicketAttachment(models.Model):

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='attachments'
    )

    tep_dinh_kem = models.FileField(
        upload_to='ticket_attachments/%Y/%m/%d/'
    )

    ten_tep_goc = models.CharField(
        max_length=255,
        blank=True
    )


    # Ma nhan dien anh nguon tu Module 2.
    # De trong voi file khong duoc gui tu M2.
    ma_anh_nguon = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        editable=False,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["ticket", "ma_anh_nguon"],
                name="unique_ticket_attachment_source",
            )
        ]


    nguoi_tai_len = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    thoi_diem_tai_len = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.ticket} - "
            f"{self.ten_tep_goc or self.tep_dinh_kem.name}"
        )
