
from django.urls import path
from . import views
from . import attachment_views

# Namespace Module 3 - Ticket Management & SLA
app_name = "tickets"

urlpatterns = [

    # ==================================================
    # UC-3.2 - DANH SACH TICKET / TICKET QUEUE
    # ==================================================
    path(
        "",
        views.ticket_home,
        name="home"
    ),

    # ==================================================
    # UC-3.x - XEM ANH BANG CHUNG TRUC TIEP
    # ==================================================
    path(
        "attachments/<int:pk>/view/",
        attachment_views.ticket_attachment_view,
        name="attachment_view"
    ),

    # ==================================================
    # UC-3.x - TAI ANH BANG CHUNG VE MAY
    # ==================================================
    path(
        "attachments/<int:pk>/download/",
        attachment_views.ticket_attachment_download,
        name="attachment_download"
    ),

    # ==================================================
    # UC-3.2 - XEM CHI TIET TICKET
    # ==================================================
    path(
        "<int:pk>/",
        views.ticket_detail,
        name="detail"
    ),

    # ==================================================
    # UC-3.2 - TIEP NHAN TICKET
    # ASSIGNED -> IN_PROGRESS
    # ==================================================
    path(
        "<int:pk>/accept/",
        views.ticket_accept,
        name="accept"
    ),

    # ==================================================
    # UC-3.3 - PHAN HOI / GHI CHU NOI BO
    # ==================================================
    path(
        "<int:pk>/messages/add/",
        views.ticket_add_message,
        name="add_message"
    ),

    # ==================================================
    # UC-3.4 - YEU CAU THAM DINH
    # ==================================================
    path(
        "<int:pk>/request-assessment/",
        views.ticket_request_assessment,
        name="request_assessment"
    ),

    # ==================================================
    # UC-3.5 - HOAN TAT XU LY
    # IN_PROGRESS -> RESOLVED
    # ==================================================
    path(
        "<int:pk>/resolve/",
        views.ticket_resolve,
        name="resolve"
    ),

    # ==================================================
    # UC-3.5 - DONG TICKET
    # RESOLVED + AGREED -> CLOSED
    # ==================================================
    path(
        "<int:pk>/close/",
        views.ticket_close,
        name="close"
    ),

    # ==================================================
    # UC-3.5 - TIEP TUC XU LY TICKET MO LAI
    # REOPENED -> IN_PROGRESS
    # ==================================================
    path(
        "<int:pk>/resume/",
        views.ticket_resume,
        name="resume"
    ),

    # ==================================================
    # UC-3.5 - KHACH HANG XEM KET QUA XU LY
    # ==================================================
    path(
        "customer/<int:pk>/result/",
        views.ticket_customer_result,
        name="customer_result"
    ),

    # ==================================================
    # UC-3.5 - KHACH HANG XAC NHAN KET QUA
    # ==================================================
    path(
        "customer/<int:pk>/confirm/",
        views.ticket_customer_confirm,
        name="customer_confirm"
    ),

    # ==================================================
    # PHAN CONG TICKET
    # ==================================================
    path(
        "<int:pk>/assign/",
        views.ticket_assign,
        name="assign"
    ),

]
