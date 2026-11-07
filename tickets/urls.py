
from django.urls import path

from . import views
from . import attachment_views
from . import customer_supplement_views


# Namespace của hệ thống quản lý Ticket
app_name = "tickets"


urlpatterns = [

    # ==================================================
    # DANH SÁCH TICKET / TICKET QUEUE
    # ==================================================
    path(
        "",
        views.ticket_home,
        name="home",
    ),

    # ==================================================
    # XEM CHI TIẾT TICKET
    # ==================================================
    path(
        "<int:pk>/",
        views.ticket_detail,
        name="detail",
    ),

    # ==================================================
    # TIẾP NHẬN TICKET
    # ASSIGNED -> IN_PROGRESS
    # ==================================================
    path(
        "<int:pk>/accept/",
        views.ticket_accept,
        name="accept",
    ),

    # ==================================================
    # PHẢN HỒI / GHI CHÚ NỘI BỘ
    # ==================================================
    path(
        "<int:pk>/messages/add/",
        views.ticket_add_message,
        name="add_message",
    ),

    # ==================================================
    # GỬI YÊU CẦU THẨM ĐỊNH
    # ==================================================
    path(
        "<int:pk>/request-assessment/",
        views.ticket_request_assessment,
        name="request_assessment",
    ),

    # ==================================================
    # HOÀN TẤT XỬ LÝ
    # IN_PROGRESS -> RESOLVED
    # ==================================================
    path(
        "<int:pk>/resolve/",
        views.ticket_resolve,
        name="resolve",
    ),

    # ==================================================
    # ĐÓNG TICKET
    # RESOLVED + AGREED -> CLOSED
    # ==================================================
    path(
        "<int:pk>/close/",
        views.ticket_close,
        name="close",
    ),

    # ==================================================
    # TIẾP TỤC XỬ LÝ TICKET MỞ LẠI
    # REOPENED -> IN_PROGRESS
    # ==================================================
    path(
        "<int:pk>/resume/",
        views.ticket_resume,
        name="resume",
    ),

    # ==================================================
    # KHÁCH HÀNG XEM KẾT QUẢ / CHI TIẾT HỖ TRỢ
    # ==================================================
    path(
        "customer/<int:pk>/result/",
        views.ticket_customer_result,
        name="customer_result",
    ),

    # ==================================================
    # KHÁCH HÀNG XÁC NHẬN KẾT QUẢ
    # ==================================================
    path(
        "customer/<int:pk>/confirm/",
        views.ticket_customer_confirm,
        name="customer_confirm",
    ),

    # ==================================================
    # KHÁCH HÀNG BỔ SUNG THÔNG TIN VÀ MINH CHỨNG
    # ==================================================
    path(
        "customer/<int:pk>/supplement/",
        customer_supplement_views.ticket_customer_supplement,
        name="customer_supplement",
    ),

    # ==================================================
    # PHÂN CÔNG TICKET
    # ==================================================
    path(
        "<int:pk>/assign/",
        views.ticket_assign,
        name="assign",
    ),

    # ==================================================
    # XEM TỆP MINH CHỨNG
    # ==================================================
    path(
        "attachments/<int:pk>/view/",
        attachment_views.ticket_attachment_view,
        name="attachment_view",
    ),

    # ==================================================
    # TẢI TỆP MINH CHỨNG
    # ==================================================
    path(
        "attachments/<int:pk>/download/",
        attachment_views.ticket_attachment_download,
        name="attachment_download",
    ),

]
