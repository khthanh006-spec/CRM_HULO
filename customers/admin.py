
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
