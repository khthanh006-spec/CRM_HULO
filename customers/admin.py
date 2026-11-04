
from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'ma_khach_hang',
        'ho_ten',
        'email',
        'so_dien_thoai',
        'thoi_diem_tao',
    )

    search_fields = (
        'ho_ten',
        'email',
        'so_dien_thoai',
    )

    list_filter = (
        'thoi_diem_tao',
    )


from django.contrib import admin
from .models import (
    LoyaltyTier,
    LoyaltyAccount,
    LoyaltyTransaction
)


# Quản lý hạng thành viên
@admin.register(LoyaltyTier)
class LoyaltyTierAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'min_total_points'
    )

    search_fields = ('code',)


# Quản lý tài khoản Loyalty
@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = (
        'customer',
        'tier',
        'points_balance',
        'total_points_earned'
    )

    search_fields = (
        'customer__ho_ten',
        'customer__email'
    )

    list_select_related = (
        'customer',
        'tier'
    )


# Quản lý lịch sử giao dịch điểm
@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'account',
        'transaction_type',
        'points',
        'description',
        'created_at'
    )

    list_filter = (
        'transaction_type',
        'created_at'
    )

    search_fields = (
        'account__customer__ho_ten',
        'description'
    )
from .models import (
    AfterSalesProgram,
    AfterSalesBenefit,
    AfterSalesDelivery,
)


class AfterSalesBenefitInline(admin.StackedInline):
    model = AfterSalesBenefit
    extra = 0

    fields = (
        'name',
        'benefit_type',
        'description',
        'terms',
        'valid_from',
        'valid_until',
        'is_enabled',
    )


@admin.register(AfterSalesProgram)
class AfterSalesProgramAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'program_type',
        'starts_at',
        'ends_at',
        'display_status',
    )

    list_filter = (
        'program_type',
        'is_enabled',
    )

    search_fields = (
        'code',
        'name',
    )

    filter_horizontal = (
        'eligible_tiers',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
    )

    fieldsets = (
        ('Thông tin chương trình', {
            'fields': (
                'code',
                'name',
                'program_type',
                'description',
            ),
        }),
        ('Thời gian và trạng thái', {
            'fields': (
                'starts_at',
                'ends_at',
                'is_enabled',
            ),
        }),
        ('Đối tượng áp dụng', {
            'fields': (
                'eligible_tiers',
            ),
            'description': (
                'Để trống nếu áp dụng cho mọi khách hàng. '
                'Nếu chọn hạng, khách hàng phải có tài khoản '
                'Loyalty thuộc một trong các hạng được chọn.'
            ),
        }),
        ('Thông tin hệ thống', {
            'fields': (
                'created_at',
                'updated_at',
            ),
        }),
    )

    inlines = (
        AfterSalesBenefitInline,
    )

    @admin.display(description='Trạng thái')
    def display_status(self, obj):
        return obj.status_label


@admin.register(AfterSalesBenefit)
class AfterSalesBenefitAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'program',
        'benefit_type',
        'valid_from',
        'valid_until',
        'is_enabled',
    )

    list_filter = (
        'benefit_type',
        'is_enabled',
    )

    search_fields = (
        'name',
        'program__code',
        'program__name',
    )

    list_select_related = (
        'program',
    )

    readonly_fields = (
        'created_at',
    )


@admin.register(AfterSalesDelivery)
class AfterSalesDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        'reference_code',
        'customer',
        'benefit',
        'channel',
        'status',
        'performed_by',
        'created_at',
    )

    list_filter = (
        'status',
        'channel',
    )

    search_fields = (
        'customer__ho_ten',
        'customer__email',
        'benefit__name',
        'benefit__program__code',
    )

    list_select_related = (
        'customer',
        'benefit',
        'benefit__program',
        'performed_by',
    )

    # Kết quả thực hiện chỉ được xem tại admin.
    # Việc cấp/gửi sẽ đi qua luồng nghiệp vụ.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False