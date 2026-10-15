
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

