from django.contrib import admin
from .models import Product, Order, OrderItem, DisputeCase

# Quản lý sản phẩm.
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("ma_san_pham", "ma_sku", "ten_san_pham")
    search_fields = ("ma_sku", "ten_san_pham")


# Quản lý đơn hàng.
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "so_don_hang",
        "ma_khach_hang",
        "trang_thai",
        "thoi_diem_dat",
        "don_vi_tien_te",
    )
    search_fields = (
        "so_don_hang",
        "ma_khach_hang__ho_ten",
    )
    list_filter = ("trang_thai", "don_vi_tien_te")


# Quản lý các dòng sản phẩm trong đơn hàng.
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "ma_chi_tiet_don",
        "ma_don_hang",
        "ma_san_pham",
        "ten_san_pham_luc_mua",
        "so_luong",
        "gia_tri_da_thanh_toan",
    )
    search_fields = (
        "ma_don_hang__so_don_hang",
        "ten_san_pham_luc_mua",
    )
@admin.register(DisputeCase)
class DisputeCaseAdmin(admin.ModelAdmin):
    list_display = (
        "ma_ho_so",
        "ma_ticket",
        "ma_nhan_vien_tham_dinh",
        "trang_thai",
        "thoi_diem_tao",
    )
    list_filter = ("trang_thai",)
    search_fields = ("ma_ticket__ma_ticket", "ma_ticket__tieu_de")
    readonly_fields = ("thoi_diem_tao", "thoi_diem_cap_nhat")