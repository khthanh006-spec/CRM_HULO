
from django.contrib import admin

from .models import (
    TicketCategory,
    TicketQueue,
    SLAConfig,
    Ticket,
    TicketLog,
    TicketMessage,
    TicketAttachment,
    TicketClassificationRule,
    TicketCategoryQueue,
)



@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'ten_danh_muc', 'dang_hoat_dong')
    search_fields = ('ten_danh_muc',)
    list_filter = ('dang_hoat_dong',)


@admin.register(TicketQueue)
class TicketQueueAdmin(admin.ModelAdmin):
    list_display = ('id', 'ten_queue', 'dang_hoat_dong')
    search_fields = ('ten_queue',)
    list_filter = ('dang_hoat_dong',)


@admin.register(SLAConfig)
class SLAConfigAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'danh_muc',
        'muc_uu_tien',
        'thoi_han_gio',
        'dang_hoat_dong',
    )
    list_filter = ('danh_muc', 'muc_uu_tien', 'dang_hoat_dong')


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'ma_ticket',
        'tieu_de',
        'khach_hang',
        'danh_muc',
        'muc_uu_tien',
        'trang_thai',
        'nguoi_phu_trach',
        'sla_deadline',
    )

    list_filter = (
        'trang_thai',
        'muc_uu_tien',
        'danh_muc',
        'queue',
    )

    search_fields = (
        'ma_ticket',
        'tieu_de',
        'khach_hang__ho_ten',
    )

    readonly_fields = ('thoi_diem_tao', 'thoi_diem_cap_nhat')


@admin.register(TicketLog)
class TicketLogAdmin(admin.ModelAdmin):
    list_display = (
        'ticket',
        'hanh_dong',
        'nguoi_thuc_hien',
        'thoi_diem',
    )
    list_filter = ('hanh_dong',)


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = (
        'ticket',
        'nguoi_gui',
        'loai_tin_nhan',
        'thoi_diem_gui',
    )
    list_filter = ('loai_tin_nhan',)


# Quản lý tệp đính kèm Ticket trong Django Admin
@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'ticket',
        'ten_tep_goc',
        'nguoi_tai_len',
        'thoi_diem_tai_len',
    )

    list_filter = ('thoi_diem_tai_len',)

    search_fields = (
        'ticket__ma_ticket',
        'ten_tep_goc',
    )

    readonly_fields = ('thoi_diem_tai_len',)

@admin.register(TicketClassificationRule)
class TicketClassificationRuleAdmin(admin.ModelAdmin):
    list_display = (
        "tu_khoa",
        "danh_muc",
        "muc_uu_tien",
        "do_uu_tien_quy_tac",
        "dang_hoat_dong",
    )
    list_filter = (
        "danh_muc",
        "muc_uu_tien",
        "dang_hoat_dong",
    )
    search_fields = ("tu_khoa",)
    ordering = ("do_uu_tien_quy_tac", "id")


@admin.register(TicketCategoryQueue)
class TicketCategoryQueueAdmin(admin.ModelAdmin):
    list_display = ("danh_muc", "queue")
    search_fields = (
        "danh_muc__ten_danh_muc",
        "queue__ten_queue",
    )
