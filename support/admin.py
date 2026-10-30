
from django.contrib import admin

from .models import (
    FAQCategory,
    FAQArticle,
    FAQFeedback,
    FAQInteraction,
)


@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ten_danh_muc",
        "dang_hien_thi",
        "thoi_diem_cap_nhat",
    )
    list_filter = ("dang_hien_thi",)
    search_fields = ("ten_danh_muc",)
    list_editable = ("dang_hien_thi",)


@admin.register(FAQArticle)
class FAQArticleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cau_hoi",
        "danh_muc",
        "dang_hien_thi",
        "thoi_diem_cap_nhat",
    )
    list_filter = (
        "dang_hien_thi",
        "danh_muc",
    )
    search_fields = (
        "cau_hoi",
        "cau_tra_loi",
    )
    list_editable = ("dang_hien_thi",)
    autocomplete_fields = ("danh_muc",)
    readonly_fields = (
        "thoi_diem_tao",
        "thoi_diem_cap_nhat",
    )


@admin.register(FAQFeedback)
class FAQFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "faq",
        "khach_hang",
        "huu_ich",
        "thoi_diem_danh_gia",
    )
    list_filter = (
        "huu_ich",
        "thoi_diem_danh_gia",
    )
    search_fields = ("faq__cau_hoi",)
    readonly_fields = (
        "faq",
        "khach_hang",
        "huu_ich",
        "thoi_diem_danh_gia",
    )

    def has_add_permission(self, request):
        return False


@admin.register(FAQInteraction)
class FAQInteractionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "faq",
        "khach_hang",
        "thoi_diem_xem",
    )
    list_filter = ("thoi_diem_xem",)
    search_fields = ("faq__cau_hoi",)
    readonly_fields = (
        "faq",
        "khach_hang",
        "thoi_diem_xem",
    )

    def has_add_permission(self, request):
        return False
