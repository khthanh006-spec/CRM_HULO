
from django.urls import path
from . import views

# Namespace của Module 3 - Ticket Management & SLA
app_name = 'tickets'

urlpatterns = [

    # ==================================================
    # UC-3.2 - DANH SÁCH TICKET / TICKET QUEUE
    # ==================================================
    path(
        '',
        views.ticket_home,
        name='home'
    ),

    # ==================================================
    # UC-3.2 - XEM CHI TIẾT TICKET
    # ==================================================
    path(
        '<int:pk>/',
        views.ticket_detail,
        name='detail'
    ),

    # ==================================================
    # UC-3.2 - TIẾP NHẬN TICKET
    # ASSIGNED -> IN_PROGRESS
    # ==================================================
    path(
        '<int:pk>/accept/',
        views.ticket_accept,
        name='accept'
    ),

    # ==================================================
    # UC-3.3 - PHẢN HỒI / GHI CHÚ NỘI BỘ
    # ==================================================
    path(
        '<int:pk>/messages/add/',
        views.ticket_add_message,
        name='add_message'
    ),

    # UC3.4 - Ghi nhận yêu cầu thẩm định
    path(
        '<int:pk>/request-assessment/',
        views.ticket_request_assessment,
        name='request_assessment'
    ),

    # ==================================================
    # UC-3.5 - HOÀN TẤT XỬ LÝ
    # IN_PROGRESS -> RESOLVED
    # ==================================================
    path(
        '<int:pk>/resolve/',
        views.ticket_resolve,
        name='resolve'
    ),

    # ==================================================
    # UC-3.5 - ĐÓNG TICKET
    # RESOLVED + AGREED -> CLOSED
    # ==================================================
    path(
        '<int:pk>/close/',
        views.ticket_close,
        name='close'
    ),

    # ==================================================
    # UC-3.5 - TIẾP TỤC XỬ LÝ TICKET MỞ LẠI
    # REOPENED -> IN_PROGRESS
    # ==================================================
    path(
        '<int:pk>/resume/',
        views.ticket_resume,
        name='resume'
    ),

    # ==================================================
    # UC-3.5 - KHÁCH HÀNG XEM KẾT QUẢ XỬ LÝ
    # ==================================================
    path(
        'customer/<int:pk>/result/',
        views.ticket_customer_result,
        name='customer_result'
    ),

    # ==================================================
    # UC-3.5 - KHÁCH HÀNG XÁC NHẬN KẾT QUẢ
    # ==================================================
    path(
        'customer/<int:pk>/confirm/',
        views.ticket_customer_confirm,
        name='customer_confirm'
    ),


    path(
        '<int:pk>/assign/',
        views.ticket_assign,
        name='assign'
    ),


]
