
from django.contrib import admin
from .models import ChatRule, ChatSession, ChatMessage


# Quản lý quy tắc trả lời Chatbot
@admin.register(ChatRule)
class ChatRuleAdmin(admin.ModelAdmin):
    list_display = (
        'ma_quy_tac',
        'ten_chu_de',
        'tu_khoa',
        'thu_tu_uu_tien',
        'dang_hoat_dong'
    )

    list_filter = (
        'dang_hoat_dong',
        'ten_chu_de'
    )

    search_fields = (
        'ten_chu_de',
        'tu_khoa'
    )

    ordering = ('-thu_tu_uu_tien',)


# Quản lý phiên trò chuyện
@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = (
        'ma_phien',
        'ma_khach_hang',
        'trang_thai',
        'ket_qua',
        'thoi_diem_bat_dau'
    )

    list_filter = (
        'trang_thai',
        'ket_qua'
    )

    search_fields = (
        'ma_khach_hang__ho_ten',
        'ma_khach_hang__email'
    )


# Quản lý lịch sử tin nhắn
@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        'ma_tin_nhan',
        'ma_phien',
        'ben_gui',
        'noi_dung',
        'thoi_diem_gui'
    )

    list_filter = ('ben_gui',)

    search_fields = ('noi_dung',)
from django.contrib import admin

# Register your models here.
