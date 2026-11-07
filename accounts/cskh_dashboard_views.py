
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Staff
from accounts.permissions import role_required
from tickets.models import (
    Ticket,
    TicketEvidenceRequest,
)


OPEN_STATUSES = [
    "NEW",
    "ASSIGNED",
    "IN_PROGRESS",
    "REOPENED",
]

MY_OPEN_STATUSES = [
    "ASSIGNED",
    "IN_PROGRESS",
    "REOPENED",
]

FINAL_STATUSES = [
    "RESOLVED",
    "CLOSED",
]


# ==========================================================
# 1. TÍNH TRẠNG THÁI SLA CHO DASHBOARD
# ==========================================================

def calculate_sla(ticket, now, warning_limit):
    """
    Tính trạng thái SLA cho Dashboard.

    Đồng bộ với logic SLA trong
    tickets.views.ticket_home().
    """

    ticket.dashboard_sla_status = "NO_SLA"
    ticket.dashboard_sla_text = "Chưa cấu hình SLA"

    if ticket.trang_thai in FINAL_STATUSES:
        ticket.dashboard_sla_status = "DONE"
        ticket.dashboard_sla_text = "Đã giải quyết"
        return ticket

    if ticket.sla_deadline is None:
        return ticket

    delta = ticket.sla_deadline - now

    total_minutes = int(
        abs(delta.total_seconds()) // 60
    )

    days, remaining_minutes = divmod(
        total_minutes,
        1440,
    )

    hours, minutes = divmod(
        remaining_minutes,
        60,
    )

    parts = []

    if days:
        parts.append(f"{days} ngày")

    if hours:
        parts.append(f"{hours} giờ")

    if minutes or not parts:
        parts.append(f"{minutes} phút")

    duration_text = " ".join(parts)

    if delta.total_seconds() <= 0:
        ticket.dashboard_sla_status = "OVERDUE"
        ticket.dashboard_sla_text = (
            f"Quá hạn {duration_text}"
        )

    elif ticket.sla_deadline <= warning_limit:
        ticket.dashboard_sla_status = "WARNING"
        ticket.dashboard_sla_text = (
            f"Còn {duration_text}"
        )

    else:
        ticket.dashboard_sla_status = "ON_TIME"
        ticket.dashboard_sla_text = (
            f"Còn {duration_text}"
        )

    return ticket


# ==========================================================
# 2. DASHBOARD NHÂN VIÊN CSKH
# ==========================================================

@role_required("CSKH")
def cskh_dashboard(request):
    """
    Dashboard cá nhân của nhân viên CSKH.

    Chỉ hiển thị:
    - Ticket NEW chưa được phân công.
    - Ticket thuộc chính nhân viên đăng nhập.

    Bổ sung:
    - Thông báo khách hàng đã gửi minh chứng
      nhưng nhân viên CSKH chưa xem.
    - Chỉ lấy thông báo thuộc Ticket của
      chính nhân viên đang phụ trách.
    """

    staff = Staff.objects.filter(
        ma_tai_khoan=request.user,
        vai_tro="CSKH",
    ).first()

    if staff is None:
        raise PermissionDenied(
            "Không tìm thấy hồ sơ nhân viên CSKH."
        )

    now = timezone.now()
    warning_limit = now + timedelta(hours=4)

    # ==========================================
    # 1. TICKET NEW TRONG HÀNG CHỜ CHUNG
    # ==========================================

    new_tickets = Ticket.objects.filter(
        trang_thai="NEW",
        nguoi_phu_trach__isnull=True,
    )

    # ==========================================
    # 2. TICKET THUỘC NHÂN VIÊN HIỆN TẠI
    # ==========================================

    my_tickets = Ticket.objects.filter(
        nguoi_phu_trach=staff,
    )

    # ==========================================
    # 3. BỐN THỐNG KÊ CHÍNH
    # ==========================================

    stats = {
        "new": new_tickets.count(),

        "assigned": my_tickets.filter(
            trang_thai="ASSIGNED"
        ).count(),

        "in_progress": my_tickets.filter(
            trang_thai="IN_PROGRESS"
        ).count(),

        "reopened": my_tickets.filter(
            trang_thai="REOPENED"
        ).count(),
    }

    # ==========================================
    # 4. THỐNG KÊ SLA
    # ==========================================

    visible_open_tickets = Ticket.objects.filter(
        Q(
            trang_thai="NEW",
            nguoi_phu_trach__isnull=True,
        )
        | Q(
            nguoi_phu_trach=staff,
            trang_thai__in=MY_OPEN_STATUSES,
        )
    )

    sla_stats = {
        "overdue": visible_open_tickets.filter(
            sla_deadline__lte=now,
        ).count(),

        "warning": visible_open_tickets.filter(
            sla_deadline__gt=now,
            sla_deadline__lte=warning_limit,
        ).count(),
    }

    # ==========================================
    # 5. TICKET CẦN ƯU TIÊN XỬ LÝ
    # ==========================================

    priority_queryset = (
        visible_open_tickets
        .select_related(
            "khach_hang",
            "danh_muc",
            "nguoi_phu_trach",
        )
        .order_by(
            "sla_deadline",
            "thoi_diem_tao",
        )
    )

    # Ticket có hạn SLA đứng trước.
    # Ticket chưa cấu hình SLA đứng sau.
    priority_tickets = sorted(
        priority_queryset,
        key=lambda ticket: (
            ticket.sla_deadline is None,
            ticket.sla_deadline
            or timezone.now() + timedelta(days=36500),
            ticket.thoi_diem_tao,
        ),
    )[:8]

    for ticket in priority_tickets:
        calculate_sla(
            ticket,
            now,
            warning_limit,
        )

    # ==========================================
    # 6. CÁC TICKET CỦA TÔI
    # ==========================================

    my_recent_tickets = list(
        my_tickets
        .select_related(
            "khach_hang",
            "danh_muc",
        )
        .order_by(
            "-thoi_diem_cap_nhat",
            "-pk",
        )[:6]
    )

    # ==========================================
    # 7. TỔNG QUAN CÁ NHÂN
    # ==========================================

    personal_stats = {
        "total": my_tickets.count(),

        "resolved": my_tickets.filter(
            trang_thai="RESOLVED"
        ).count(),

        "closed": my_tickets.filter(
            trang_thai="CLOSED"
        ).count(),

        "assessment_waiting": my_tickets.filter(
            trang_thai_tham_dinh="WAITING"
        ).count(),
    }

    # ==========================================
    # 8. THÔNG BÁO KHÁCH HÀNG BỔ SUNG MINH CHỨNG
    # ==========================================

    evidence_notifications_queryset = (
        TicketEvidenceRequest.objects.filter(
            ticket__nguoi_phu_trach=staff,
            trang_thai="FULFILLED",
            thoi_diem_cskh_xem__isnull=True,
            tin_nhan_phan_hoi__isnull=False,
        )
        .select_related(
            "ticket",
            "ticket__khach_hang",
            "tin_nhan_yeu_cau",
            "tin_nhan_phan_hoi",
        )
        .order_by(
            "-thoi_diem_hoan_thanh",
            "-pk",
        )
    )

    # Đếm đầy đủ số thông báo chưa xem.
    evidence_notifications_count = (
        evidence_notifications_queryset.count()
    )

    # Hiển thị tối đa 10 thông báo mới nhất.
    evidence_notifications = list(
        evidence_notifications_queryset[:10]
    )

    # Thông báo mới nhất dùng cho popup.
    evidence_notification_latest = None

    if evidence_notifications:
        evidence_notification_latest = (
            evidence_notifications[0]
        )

    # ==========================================
    # 9. TRUYỀN DỮ LIỆU SANG TEMPLATE
    # ==========================================

    context = {
        "staff": staff,
        "stats": stats,
        "sla_stats": sla_stats,
        "personal_stats": personal_stats,
        "priority_tickets": priority_tickets,
        "my_recent_tickets": my_recent_tickets,

        # Thông báo khách hàng bổ sung minh chứng.
        "evidence_notifications": (
            evidence_notifications
        ),
        "evidence_notifications_count": (
            evidence_notifications_count
        ),
        "evidence_notification_latest": (
            evidence_notification_latest
        ),
    }

    return render(
        request,
        "accounts/cskh_dashboard.html",
        context,
    )


# ==========================================================
# 3. CSKH XEM MINH CHỨNG KHÁCH HÀNG BỔ SUNG
# ==========================================================

@role_required("CSKH")
@require_POST
def cskh_view_evidence_notification(request, request_id):
    """
    Ghi nhận CSKH đã xem thông báo minh chứng.

    Quy tắc:
    1. Chỉ tài khoản CSKH được thao tác.
    2. Chỉ CSKH đang phụ trách Ticket mới có quyền xem.
    3. Yêu cầu phải ở trạng thái FULFILLED.
    4. Phải có tin nhắn phản hồi của khách hàng.
    5. Chỉ ghi thời điểm xem một lần.
    6. Không thay đổi trạng thái Ticket.
    7. Chuyển đến đúng trang chi tiết Ticket.
    """

    # ==========================================
    # 1. XÁC ĐỊNH NHÂN VIÊN HIỆN TẠI
    # ==========================================

    staff = Staff.objects.filter(
        ma_tai_khoan=request.user,
        vai_tro="CSKH",
    ).first()

    if staff is None:
        raise PermissionDenied(
            "Không tìm thấy hồ sơ nhân viên CSKH."
        )

    # ==========================================
    # 2. KIỂM TRA VÀ CẬP NHẬT TRONG TRANSACTION
    # ==========================================

    with transaction.atomic():

        evidence_request = get_object_or_404(
            TicketEvidenceRequest.objects
            .select_for_update()
            .select_related("ticket"),
            pk=request_id,
            ticket__nguoi_phu_trach=staff,
            trang_thai="FULFILLED",
            tin_nhan_phan_hoi__isnull=False,
        )

        # Chỉ ghi nhận lần đầu xem minh chứng.
        if evidence_request.thoi_diem_cskh_xem is None:

            evidence_request.thoi_diem_cskh_xem = (
                timezone.now()
            )

            evidence_request.save(
                update_fields=[
                    "thoi_diem_cskh_xem",
                ]
            )

        ticket_id = evidence_request.ticket_id

    # ==========================================
    # 3. MỞ ĐÚNG TICKET
    # ==========================================

    ticket_url = reverse(
        "tickets:detail",
        kwargs={"pk": ticket_id},
    )

    # Đưa nhân viên đến phần lịch sử trao đổi.
    # Tại đây có tin nhắn khách hàng gửi bổ sung.
    return redirect(
        ticket_url + "#ticket-conversation"
    )
