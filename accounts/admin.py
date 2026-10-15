
from django.contrib import admin
from .models import Staff


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = (
        'ma_nhan_vien',
        'ho_ten',
        'email',
        'vai_tro',
        'san_sang_nhan_viec',
    )

    list_filter = (
        'vai_tro',
        'san_sang_nhan_viec',
    )

    search_fields = (
        'ho_ten',
        'email',
        'so_dien_thoai',
    )

