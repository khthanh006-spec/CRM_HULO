
from django.db.models import Count, Q

from accounts.models import Staff
from .models import Ticket, TicketQueue


def chon_nhan_vien_cskh():
    """
    Chọn nhân viên CSKH phù hợp để nhận Ticket.

    Điều kiện:
    - Có vai trò CSKH.
    - Sẵn sàng nhận việc.
    - Tài khoản đang hoạt động.
    - Ưu tiên người có ít Ticket đang mở nhất.
    """

    nhan_vien = (
        Staff.objects.filter(
            vai_tro="CSKH",
            san_sang_nhan_viec=True,
            ma_tai_khoan__is_active=True,
        )
        .annotate(
            so_ticket_dang_mo=Count(
                "tickets_duoc_giao",
                filter=Q(
                    tickets_duoc_giao__trang_thai__in=[
                        "ASSIGNED",
                        "IN_PROGRESS",
                        "REOPENED",
                    ]
                ),
            )
        )
        .order_by(
            "so_ticket_dang_mo",
            "pk",
        )
        .first()
    )

    return nhan_vien


def tim_queue_san_pham():
    """
    Tìm hàng đợi đang hoạt động
    dành cho vấn đề sản phẩm.
    """

    return TicketQueue.objects.filter(
        ten_queue="CSKH - Sản phẩm",
        dang_hoat_dong=True,
    ).first()
