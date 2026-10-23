
from django.urls import path
from . import views

# Namespace Module 3 - Ticket Management & SLA
app_name = 'tickets'

urlpatterns = [

    # ==========================================
    # UC-3.2 - DANH SÁCH TICKET
    # ==========================================
    path(
        '',
        views.ticket_home,
        name='home'
    ),

    # ==========================================
    # UC-3.2 - CHI TIẾT TICKET CỦA NHÂN VIÊN
    # ==========================================
    path(
        '<int:pk>/',
        views.ticket_detail,
        name='detail'
    ),

    # ==========================================
    # UC-3.2 - TIẾP NHẬN TICKET
    # ASSIGNED -> IN_PROGRESS
    # ==========================================
    path(
        '<int:pk>/accept/',
        views.ticket_accept,
        name='accept'
    ),

    # ==========================================
    # UC-3.3 - PHẢN HỒI / GHI CHÚ NỘI BỘ
    # ==========================================
    path(
        '<int:pk>/messages/add/',
        views.ticket_add_message,
        name='add_message'
    ),

    # ==========================================
    # UC-3.5 - HOÀN TẤT XỬ LÝ
    # IN_PROGRESS -> RESOLVED
    # ==========================================
    path(
        '<int:pk>/resolve/',
        views.ticket_resolve,
        name='resolve'
    ),

    # ==========================================
    # UC-3.5 - TIẾP TỤC XỬ LÝ TICKET MỞ LẠI
    # REOPENED -> IN_PROGRESS
    # ==========================================
    path(
        '<int:pk>/resume/',
        views.ticket_resume,
        name='resume'
    ),

    # ==========================================
    # UC-3.5 - KHÁCH HÀNG XEM KẾT QUẢ
    # ==========================================
    path(
        'customer/<int:pk>/result/',
        views.ticket_customer_result,
        name='customer_result'
    ),

    # ==========================================
    # UC-3.5 - KHÁCH HÀNG XÁC NHẬN KẾT QUẢ
    # ==========================================
    path(
        'customer/<int:pk>/confirm/',
        views.ticket_customer_confirm,
        name='customer_confirm'
    ),

]
