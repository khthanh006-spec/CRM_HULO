from django.contrib import admin
from .models import Product, Order, OrderItem


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