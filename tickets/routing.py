
from django.db.models import Count, Q

from accounts.models import Staff
from .models import Ticket, TicketQueue


# Quy tắc phân luồng theo danh mục Ticket M3.
# Tên danh mục và Queue phải khớp dữ liệu hiện có.
BANG_PHAN_LUONG = {
    "Hàng bị lỗi": "CSKH - Sản phẩm",
    "Lỗi in ấn": "CSKH - Sản phẩm",
    "Sai thiết kế cá nhân hóa": "CSKH - Sản phẩm",

    "Sai sản phẩm / đơn hàng": "CSKH - Đơn hàng và vận chuyển",
    "Thiếu sản phẩm / phụ kiện": "CSKH - Đơn hàng và vận chuyển",
    "Chậm sản xuất": "CSKH - Đơn hàng và vận chuyển",
    "Chậm giao hàng": "CSKH - Đơn hàng và vận chuyển",
    "Hư hỏng khi vận chuyển": "CSKH - Đơn hàng và vận chuyển",
    "Hủy / Thay đổi đơn hàng": "CSKH - Đơn hàng và vận chuyển",

    "Đổi trả / Hoàn tiền": "CSKH - Đổi trả và hậu mãi",
    "Bảo hành / Hậu mãi": "CSKH - Đổi trả và hậu mãi",

    "Thanh toán / Hóa đơn": "CSKH - Thanh toán và dịch vụ",
    "Khiếu nại dịch vụ": "CSKH - Thanh toán và dịch vụ",
}


def chon_nhan_vien_cskh():
    """
    Chọn nhân viên CSKH phù hợp để nhận Ticket.

    Điều kiện:
    - Có vai trò CSKH.
    - Sẵn sàng nhận việc.
    - Tài khoản đang hoạt động.
    - Ưu tiên người có ít Ticket đang mở nhất.

    Hiện tại Staff chưa liên kết với Queue,
    nên lựa chọn theo khối lượng công việc chung.
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


def tim_queue_theo_danh_muc(danh_muc):
    """
    Tìm Queue đang hoạt động theo danh mục Ticket.

    Trả về None nếu:
    - Danh mục không hợp lệ.
    - Danh mục chưa được cấu hình.
    - Queue tương ứng không tồn tại hoặc ngừng hoạt động.
    """

    if danh_muc is None:
        return None

    ten_danh_muc = getattr(
        danh_muc,
        "ten_danh_muc",
        None,
    )

    if not ten_danh_muc:
        return None

    ten_queue = BANG_PHAN_LUONG.get(ten_danh_muc)

    if not ten_queue:
        return None

    return TicketQueue.objects.filter(
        ten_queue=ten_queue,
        dang_hoat_dong=True,
    ).first()


def tim_queue_san_pham():
    """
    Giữ hàm cũ để tương thích với các phần
    khác của hệ thống có thể đang sử dụng.
    """

    return TicketQueue.objects.filter(
        ten_queue="CSKH - Sản phẩm",
        dang_hoat_dong=True,
    ).first()
