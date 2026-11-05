from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone



# ==========================================
# KHÁCH HÀNG
# ==========================================

class Customer(models.Model):
    ma_khach_hang = models.AutoField(primary_key=True)

    ma_tai_khoan = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='customer_profile',
    )

    ho_ten = models.CharField(max_length=150)
    email = models.EmailField(unique=True)

    so_dien_thoai = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    dia_chi_mac_dinh = models.TextField(
        blank=True,
        null=True,
    )

    thoi_diem_tao = models.DateTimeField(auto_now_add=True)
    thoi_diem_cap_nhat = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.ma_khach_hang} - {self.ho_ten}'


# ==========================================
# LOYALTY
# ==========================================

class LoyaltyTier(models.Model):
    class TierCode(models.TextChoices):
        MEMBER = 'MEMBER', 'Member'
        SILVER = 'SILVER', 'Silver'
        GOLD = 'GOLD', 'Gold'
        PLATINUM = 'PLATINUM', 'Platinum'

    code = models.CharField(
        max_length=20,
        choices=TierCode.choices,
        unique=True,
    )

    min_total_points = models.PositiveIntegerField(default=0)
    benefits = models.TextField(blank=True)

    def __str__(self):
        return self.get_code_display()


class LoyaltyAccount(models.Model):
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name='loyalty_account',
    )

    tier = models.ForeignKey(
        LoyaltyTier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='accounts',
    )

    points_balance = models.PositiveIntegerField(default=0)
    total_points_earned = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Loyalty - {self.customer.ho_ten}'


class LoyaltyTransaction(models.Model):
    class TransactionType(models.TextChoices):
        EARN = 'EARN', 'Cộng điểm'
        REDEEM = 'REDEEM', 'Đổi điểm'

    account = models.ForeignKey(
        LoyaltyAccount,
        on_delete=models.PROTECT,
        related_name='transactions',
    )

    transaction_type = models.CharField(
        max_length=10,
        choices=TransactionType.choices,
    )

    points = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    description = models.CharField(max_length=255, blank=True)

    idempotency_key = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='loyalty_transactions_performed',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f'{self.get_transaction_type_display()}'
            f' - {self.points} điểm'
        )


# ==========================================
# LỊCH SỬ CHĂM SÓC
# ==========================================

class CareRecord(models.Model):
    class CareType(models.TextChoices):
        NOTE = 'NOTE', 'Ghi chú nội bộ'
        CALL = 'CALL', 'Gọi điện'
        MESSAGE = 'MESSAGE', 'Nhắn tin'
        OTHER = 'OTHER', 'Khác'

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='care_records',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='m5_care_records_created',
    )

    care_type = models.CharField(
        max_length=12,
        choices=CareType.choices,
        default=CareType.NOTE,
    )

    content = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    # Hoạt động chăm sóc thông thường có thể không thuộc ca.
    retention_case = models.ForeignKey(
        'RetentionCase',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='care_records',
        verbose_name='Ca giữ chân',
    )

    class Meta:
        ordering = ['-created_at', '-pk']

    def clean(self):
        super().clean()

        if self.retention_case_id:
            if self.customer_id != self.retention_case.customer_id:
                raise ValidationError({
                    'retention_case': (
                        'Ca giữ chân phải thuộc khách hàng '
                        'được chăm sóc.'
                    ),
                })

    def __str__(self):
        return f'CARE{self.pk or 0:03d} - {self.customer.ho_ten}'


# ==========================================
# CSAT
# ==========================================

class CSAT(models.Model):
    ticket = models.OneToOneField(
        'tickets.Ticket',
        on_delete=models.PROTECT,
        related_name='csat',
    )

    score = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
    )

    comment = models.TextField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

        constraints = [
            models.CheckConstraint(
                condition=models.Q(score__gte=1, score__lte=5),
                name='m5_csat_score_1_to_5',
            ),
        ]

    def __str__(self):
        return f'CSAT - {self.ticket} - {self.score}/5 sao'

    @property
    def is_low_score(self):
        return self.score <= 3


# ==========================================
# CA GIỮ CHÂN KHÁCH HÀNG
# ==========================================

class RetentionCase(models.Model):
    class Source(models.TextChoices):
        LOW_CSAT = 'LOW_CSAT', 'CSAT 1–2 sao'
        REOPENED = 'REOPENED', 'Khách hàng yêu cầu mở lại Ticket'

    class RiskLevel(models.TextChoices):
        HIGH = 'HIGH', 'Cao'
        MEDIUM = 'MEDIUM', 'Trung bình'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Chờ xử lý'
        IN_PROGRESS = 'IN_PROGRESS', 'Đang chăm sóc'
        SAVED = 'SAVED', 'Hài lòng lại'
        UNSUCCESSFUL = 'UNSUCCESSFUL', 'Chưa giữ chân được'

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='retention_cases',
        verbose_name='Khách hàng',
    )

    ticket = models.ForeignKey(
        'tickets.Ticket',
        on_delete=models.PROTECT,
        related_name='retention_cases',
        verbose_name='Ticket liên quan',
    )

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        verbose_name='Nguồn kích hoạt',
    )

    # Một đánh giá CSAT chỉ tạo tối đa một ca.
    source_csat = models.OneToOneField(
        CSAT,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='retention_case',
        verbose_name='Đánh giá CSAT nguồn',
    )

    # Mỗi lần mở lại có một TicketLog riêng.
    # Không phụ thuộc vào trạng thái hiện tại của Ticket.
    source_ticket_log = models.OneToOneField(
        'tickets.TicketLog',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='retention_case',
        verbose_name='Sự kiện mở lại Ticket',
    )

    risk_level = models.CharField(
        max_length=10,
        choices=RiskLevel.choices,
        default=RiskLevel.HIGH,
        verbose_name='Mức rủi ro',
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Trạng thái',
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='assigned_retention_cases',
        verbose_name='Nhân viên phụ trách',
    )

    trigger_summary = models.TextField(
        max_length=1000,
        blank=True,
        verbose_name='Tóm tắt nguyên nhân',
    )

    resolution_note = models.TextField(
        max_length=2000,
        blank=True,
        verbose_name='Kết quả xử lý',
    )

    customer_feedback = models.TextField(
        max_length=2000,
        blank=True,
        verbose_name='Phản hồi khách hàng',
    )

    satisfaction_confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Thời điểm khách hàng xác nhận hài lòng',
    )

    # Thời điểm của đánh giá hoặc log nguồn.
    triggered_at = models.DateTimeField(
        verbose_name='Thời điểm phát sinh',
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Thời điểm tiếp nhận',
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Thời điểm kết thúc',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-triggered_at', '-pk']
        verbose_name = 'Ca giữ chân'
        verbose_name_plural = 'Ca giữ chân'

        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        source='LOW_CSAT',
                        source_csat__isnull=False,
                        source_ticket_log__isnull=True,
                    )
                    | models.Q(
                        source='REOPENED',
                        source_csat__isnull=True,
                        source_ticket_log__isnull=False,
                    )
                ),
                name='m5_retention_valid_source',
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status='SAVED')
                    | (
                        models.Q(
                            satisfaction_confirmed_at__isnull=False,
                        )
                        & ~models.Q(customer_feedback='')
                        & ~models.Q(resolution_note='')
                    )
                ),
                name='m5_retention_saved_evidence',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status__in=['PENDING', 'IN_PROGRESS'],
                        closed_at__isnull=True,
                    )
                    | models.Q(
                        status__in=['SAVED', 'UNSUCCESSFUL'],
                        closed_at__isnull=False,
                    )
                ),
                name='m5_retention_closed_state',
            ),
        ]

    @property
    def case_code(self):
        return f'RC{self.pk:05d}' if self.pk else 'RC-MỚI'

    def __str__(self):
        return f'{self.case_code} - {self.customer.ho_ten}'

    def clean(self):
        super().clean()
        errors = {}

        if self.ticket_id:
            if self.ticket.khach_hang_id != self.customer_id:
                errors['ticket'] = (
                    'Ticket không thuộc khách hàng của ca.'
                )

        if self.source == self.Source.LOW_CSAT:
            if not self.source_csat_id or self.source_ticket_log_id:
                errors['source'] = (
                    'Ca CSAT phải có đúng một đánh giá nguồn '
                    'và không có log mở lại.'
                )
            else:
                if self.source_csat.ticket_id != self.ticket_id:
                    errors['source_csat'] = (
                        'Đánh giá CSAT không thuộc Ticket của ca.'
                    )
                elif self.source_csat.score not in [1, 2]:
                    errors['source_csat'] = (
                        'Ca khẩn cấp chỉ nhận CSAT 1 hoặc 2 sao.'
                    )

        elif self.source == self.Source.REOPENED:
            if not self.source_ticket_log_id or self.source_csat_id:
                errors['source'] = (
                    'Ca mở lại phải có đúng một log nguồn '
                    'và không có đánh giá CSAT nguồn.'
                )
            else:
                log = self.source_ticket_log

                if log.ticket_id != self.ticket_id:
                    errors['source_ticket_log'] = (
                        'Log không thuộc Ticket của ca.'
                    )
                elif log.hanh_dong != 'KHÁCH HÀNG YÊU CẦU MỞ LẠI':
                    errors['source_ticket_log'] = (
                        'Log được chọn không phải sự kiện mở lại.'
                    )

        if self.status != self.Status.PENDING:
            if not self.assigned_to_id or not self.started_at:
                errors['status'] = (
                    'Ca đã xử lý phải có nhân viên phụ trách '
                    'và thời điểm tiếp nhận.'
                )

        if self.status in [
            self.Status.SAVED,
            self.Status.UNSUCCESSFUL,
        ]:
            if not self.closed_at:
                errors['closed_at'] = (
                    'Cần ghi thời điểm kết thúc ca.'
                )

            if not self.resolution_note.strip():
                errors['resolution_note'] = (
                    'Cần ghi kết quả xử lý trước khi kết thúc.'
                )

        elif self.closed_at:
            errors['closed_at'] = (
                'Ca chưa kết thúc không có thời điểm đóng.'
            )

        if self.status == self.Status.SAVED:
            if not self.customer_feedback.strip():
                errors['customer_feedback'] = (
                    'Cần ghi phản hồi xác nhận hài lòng '
                    'của khách hàng.'
                )

            if not self.satisfaction_confirmed_at:
                errors['satisfaction_confirmed_at'] = (
                    'Cần ghi thời điểm xác nhận hài lòng.'
                )

        if errors:
            raise ValidationError(errors)


# ==========================================
# CHƯƠNG TRÌNH CHĂM SÓC & HẬU MÃI
# ==========================================

class AfterSalesProgram(models.Model):
    class ProgramType(models.TextChoices):
        APPRECIATION = 'APPRECIATION', 'Tri ân khách hàng'
        HOLIDAY = 'HOLIDAY', 'Lễ / Tết'
        RETENTION = 'RETENTION', 'Chăm sóc giữ chân'

    code = models.CharField(
        'Mã chương trình',
        max_length=30,
        unique=True,
    )

    name = models.CharField('Tên chương trình', max_length=150)

    program_type = models.CharField(
        'Loại chương trình',
        max_length=20,
        choices=ProgramType.choices,
        default=ProgramType.APPRECIATION,
    )

    description = models.TextField(
        'Nội dung chương trình',
        blank=True,
    )

    starts_at = models.DateTimeField('Thời gian bắt đầu')
    ends_at = models.DateTimeField('Thời gian kết thúc')

    is_enabled = models.BooleanField(
        'Cho phép triển khai',
        default=True,
    )

    eligible_tiers = models.ManyToManyField(
        LoyaltyTier,
        blank=True,
        related_name='after_sales_programs',
        verbose_name='Hạng Loyalty được áp dụng',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-starts_at', '-pk']

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    ends_at__gt=models.F('starts_at'),
                ),
                name='m5_after_sales_program_dates',
            ),
        ]

    def __str__(self):
        return f'{self.code} - {self.name}'

    def clean(self):
        super().clean()

        if (
            self.starts_at
            and self.ends_at
            and self.ends_at <= self.starts_at
        ):
            raise ValidationError({
                'ends_at': (
                    'Thời gian kết thúc phải sau '
                    'thời gian bắt đầu.'
                ),
            })

    @property
    def status(self):
        now = timezone.now()

        if not self.is_enabled:
            return 'PAUSED'
        if now < self.starts_at:
            return 'UPCOMING'
        if now > self.ends_at:
            return 'EXPIRED'
        return 'ACTIVE'

    @property
    def status_label(self):
        return {
            'PAUSED': 'Tạm dừng',
            'UPCOMING': 'Sắp diễn ra',
            'EXPIRED': 'Hết hạn',
            'ACTIVE': 'Đang hiệu lực',
        }[self.status]

    @property
    def is_active(self):
        return self.status == 'ACTIVE'


# ==========================================
# VOUCHER / QUYỀN LỢI
# ==========================================

class AfterSalesBenefit(models.Model):
    class BenefitType(models.TextChoices):
        VOUCHER = 'VOUCHER', 'Voucher'
        PRIVILEGE = 'PRIVILEGE', 'Quyền lợi'

    program = models.ForeignKey(
        AfterSalesProgram,
        on_delete=models.PROTECT,
        related_name='benefits',
        verbose_name='Chương trình',
    )

    name = models.CharField('Tên quyền lợi', max_length=150)

    benefit_type = models.CharField(
        'Loại quyền lợi',
        max_length=20,
        choices=BenefitType.choices,
        default=BenefitType.VOUCHER,
    )

    description = models.TextField(
        'Nội dung quyền lợi',
        max_length=1000,
    )

    terms = models.TextField('Điều kiện sử dụng', blank=True)
    valid_from = models.DateTimeField('Có hiệu lực từ')
    valid_until = models.DateTimeField('Hết hiệu lực lúc')

    is_enabled = models.BooleanField(
        'Cho phép cấp quyền lợi',
        default=True,
    )

    # Phân loại rõ để thống kê Voucher đền bù.
    is_apology = models.BooleanField(
        'Voucher đền bù / xin lỗi',
        default=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'pk']

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    valid_until__gt=models.F('valid_from'),
                ),
                name='m5_after_sales_benefit_dates',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_apology=False)
                    | models.Q(benefit_type='VOUCHER')
                ),
                name='m5_apology_requires_voucher',
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        errors = {}

        if (
            self.valid_from
            and self.valid_until
            and self.valid_until <= self.valid_from
        ):
            errors['valid_until'] = (
                'Hạn sử dụng phải sau thời gian bắt đầu hiệu lực.'
            )

        if (
            self.is_apology
            and self.benefit_type != self.BenefitType.VOUCHER
        ):
            errors['is_apology'] = (
                'Chỉ Voucher được phân loại là Voucher đền bù.'
            )

        if errors:
            raise ValidationError(errors)

    @property
    def is_active(self):
        now = timezone.now()

        return (
            self.is_enabled
            and self.valid_from <= now <= self.valid_until
            and self.program.is_active
        )


# ==========================================
# KẾT QUẢ CẤP / GỬI QUYỀN LỢI
# ==========================================

class AfterSalesDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Chờ xử lý'
        ISSUED = 'ISSUED', 'Đã cấp quyền lợi'
        SENT = 'SENT', 'Đã gửi thành công'
        FAILED = 'FAILED', 'Gửi thất bại'

    class Channel(models.TextChoices):
        INTERNAL = 'INTERNAL', 'Ghi nhận trên CRM'
        EMAIL = 'EMAIL', 'Email'

    benefit = models.ForeignKey(
        AfterSalesBenefit,
        on_delete=models.PROTECT,
        related_name='deliveries',
        verbose_name='Quyền lợi',
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='after_sales_deliveries',
        verbose_name='Khách hàng',
    )

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='after_sales_deliveries_performed',
        verbose_name='Người thực hiện',
    )

    care_record = models.OneToOneField(
        CareRecord,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='after_sales_delivery',
    )

    retention_case = models.ForeignKey(
        RetentionCase,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='voucher_deliveries',
        verbose_name='Ca giữ chân',
    )

    # Lưu phân loại tại lúc cấp, tránh thống kê quá khứ
    # thay đổi khi sửa phân loại của mẫu Voucher.
    is_apology = models.BooleanField(
        'Đã cấp với mục đích đền bù',
        default=False,
        editable=False,
    )

    reference_code = models.UUIDField(
        default=uuid4,
        unique=True,
        editable=False,
    )

    channel = models.CharField(
        max_length=12,
        choices=Channel.choices,
        default=Channel.INTERNAL,
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )

    message_content = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    attempt_count = models.PositiveIntegerField(default=0)

    issued_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']

        constraints = [
            models.UniqueConstraint(
                fields=['benefit', 'customer'],
                name='m5_unique_benefit_customer',
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.retention_case_id:
            if self.retention_case.customer_id != self.customer_id:
                errors['retention_case'] = (
                    'Ca giữ chân không thuộc khách hàng nhận Voucher.'
                )

        if self.care_record_id:
            record = self.care_record

            if record.customer_id != self.customer_id:
                errors['care_record'] = (
                    'Lịch sử chăm sóc không thuộc khách hàng nhận.'
                )
            elif record.retention_case_id != self.retention_case_id:
                errors['care_record'] = (
                    'Lịch sử chăm sóc và lượt cấp phải '
                    'liên kết cùng ca giữ chân.'
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f'{self.customer.ho_ten} - '
            f'{self.benefit.name} - '
            f'{self.get_status_display()}'
        )
class LoyaltyReward(models.Model):
    name = models.CharField(
        'Tên Voucher',
        max_length=150,
        unique=True,
    )

    points_cost = models.PositiveIntegerField(
        'Điểm cần đổi',
        validators=[MinValueValidator(1)],
    )

    discount_amount = models.PositiveIntegerField(
        'Giá trị giảm (VNĐ)',
        validators=[MinValueValidator(1)],
    )

    terms = models.TextField(
        'Điều kiện sử dụng',
        blank=True,
    )

    validity_days = models.PositiveIntegerField(
        'Số ngày hiệu lực sau khi đổi',
        default=30,
        validators=[MinValueValidator(1)],
    )

    is_enabled = models.BooleanField(
        'Cho phép đổi',
        default=True,
    )

    class Meta:
        ordering = ['points_cost', 'pk']

    def __str__(self):
        return f'{self.name} - {self.points_cost} điểm'


class LoyaltyRedemption(models.Model):
    # Một giao dịch trừ điểm chỉ tạo một Voucher.
    transaction = models.OneToOneField(
        LoyaltyTransaction,
        on_delete=models.PROTECT,
        related_name='voucher_redemption',
    )

    reward = models.ForeignKey(
        LoyaltyReward,
        on_delete=models.PROTECT,
        related_name='redemptions',
    )

    reference_code = models.UUIDField(
        default=uuid4,
        unique=True,
        editable=False,
    )

    # Chụp lại thông tin tại thời điểm đổi.
    # Sửa mẫu Voucher không thay đổi Voucher đã cấp.
    voucher_name = models.CharField(max_length=150)
    points_spent = models.PositiveIntegerField()
    discount_amount = models.PositiveIntegerField()
    terms = models.TextField(blank=True)

    issued_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-issued_at', '-pk']

    def __str__(self):
        return f'{self.voucher_name} - {self.reference_code}'