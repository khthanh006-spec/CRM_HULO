from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.conf import settings


class Customer(models.Model):

    ma_khach_hang = models.AutoField(
        primary_key=True
    )

    ma_tai_khoan = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='customer_profile'
    )

    ho_ten = models.CharField(
        max_length=150
    )

    email = models.EmailField(
        unique=True
    )

    so_dien_thoai = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    dia_chi_mac_dinh = models.TextField(
        blank=True,
        null=True
    )

    thoi_diem_tao = models.DateTimeField(
        auto_now_add=True
    )

    thoi_diem_cap_nhat = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.ma_khach_hang} - {self.ho_ten}"

# MODULE 5 - LOYALTY


class LoyaltyTier(models.Model):
    class TierCode(models.TextChoices):
        MEMBER = 'MEMBER', 'Member'
        SILVER = 'SILVER', 'Silver'
        GOLD = 'GOLD', 'Gold'
        PLATINUM = 'PLATINUM', 'Platinum'

    code = models.CharField(
        max_length=20,
        choices=TierCode.choices,
        unique=True
    )

    min_total_points = models.PositiveIntegerField(
        default=0
    )

    benefits = models.TextField(
        blank=True
    )

    def __str__(self):
        return self.get_code_display()


class LoyaltyAccount(models.Model):
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name='loyalty_account'
    )

    tier = models.ForeignKey(
        LoyaltyTier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='accounts'
    )

    points_balance = models.PositiveIntegerField(
        default=0
    )

    total_points_earned = models.PositiveIntegerField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"Loyalty - {self.customer.ho_ten}"



class LoyaltyTransaction(models.Model):

    class TransactionType(models.TextChoices):
        EARN = 'EARN', 'Cộng điểm'
        REDEEM = 'REDEEM', 'Đổi điểm'

    # Tài khoản Loyalty được cộng / đổi điểm
    account = models.ForeignKey(
        LoyaltyAccount,
        on_delete=models.PROTECT,
        related_name='transactions'
    )

    # Loại giao dịch
    transaction_type = models.CharField(
        max_length=10,
        choices=TransactionType.choices
    )

    # Số điểm giao dịch
    points = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    # Lý do giao dịch
    description = models.CharField(
        max_length=255,
        blank=True
    )

    # MỚI: Mã nhận diện yêu cầu giao dịch
    idempotency_key = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        editable=False
    )

    # MỚI: Người thực hiện giao dịch
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='loyalty_transactions_performed'
    )

    # Thời điểm giao dịch
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.get_transaction_type_display()}"
            f" - {self.points} điểm"
        )


# ==========================================
# MODULE 5 - QUAN LY CHAM SOC KHACH HANG
# ==========================================

class CareRecord(models.Model):

    class CareType(models.TextChoices):
        NOTE = 'NOTE', 'Ghi chú nội bộ'
        CALL = 'CALL', 'Gọi điện'
        MESSAGE = 'MESSAGE', 'Nhắn tin'
        OTHER = 'OTHER', 'Khác'

    # Khách hàng được chăm sóc
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='care_records'
    )

    # Nhân viên thực hiện
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='m5_care_records_created'
    )

    # Hình thức chăm sóc
    care_type = models.CharField(
        max_length=12,
        choices=CareType.choices,
        default=CareType.NOTE
    )

    # Nội dung chăm sóc
    content = models.TextField(
        max_length=500
    )

    # Thời gian ghi nhận
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return (
            f"CARE{self.pk or 0:03d} - "
            f"{self.customer.ho_ten}"
        )


# ==========================================
# MODULE 5 - DANH GIA MUC DO HAI LONG CSAT
# ==========================================

class CSAT(models.Model):

    # Moi Ticket chi duoc danh gia mot lan
    ticket = models.OneToOneField(
        'tickets.Ticket',
        on_delete=models.PROTECT,
        related_name='csat'
    )

    # Diem danh gia tu 1 den 5 sao
    score = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ]
    )

    # Nhan xet cua khach hang
    comment = models.TextField(
        max_length=500,
        blank=True
    )

    # Thoi diem khach hang danh gia
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['-created_at']

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    score__gte=1,
                    score__lte=5
                ),
                name='m5_csat_score_1_to_5'
            )
        ]

    def __str__(self):
        return (
            f"CSAT - {self.ticket} - "
            f"{self.score}/5 sao"
        )

    @property
    def is_low_score(self):
        return self.score <= 3
