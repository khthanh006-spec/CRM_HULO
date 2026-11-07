
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone

from accounts.models import Staff
from accounts.permissions import get_user_role
from customers.models import CSAT
from disputes.models import (
    CompensationAction,
    DisputeCase,
)
from tickets.models import Ticket


OPEN_TICKET_STATUSES = (
    "ASSIGNED",
    "IN_PROGRESS",
    "REOPENED",
)

FINAL_TICKET_STATUSES = (
    "RESOLVED",
    "CLOSED",
)

OPEN_DISPUTE_STATUSES = (
    "CHO_TIEP_NHAN",
    "DANG_THAM_DINH",
    "CHO_BO_SUNG",
)


@login_required(login_url="login")
def manager_dashboard(request):
    """
    Dashboard quản lý vận hành CRM HULO.

    Giữ nguyên:
    - Tổng quan Ticket M3.
    - Tổng quan hồ sơ thẩm định M4.
    - Thống kê CSAT M5.
    - Thống kê nhân viên.
    - Bộ lọc và phân trang Ticket.

    Bổ sung:
    - Danh sách phương án hoàn tiền CHO_DUYET.
    - Dữ liệu thông báo tự động cho MANAGER.
    """

    role = get_user_role(request.user)

    if role != "MANAGER":
        return HttpResponseForbidden(
            "Bạn không có quyền truy cập Dashboard quản lý."
        )

    now = timezone.now()

    tickets = Ticket.objects.all()
    disputes = DisputeCase.objects.all()

    # ==========================================
    # 1. TỔNG QUAN TICKET M3
    # ==========================================

    ticket_stats = {
        "total": tickets.count(),
        "new": tickets.filter(
            trang_thai="NEW"
        ).count(),
        "assigned": tickets.filter(
            trang_thai="ASSIGNED"
        ).count(),
        "in_progress": tickets.filter(
            trang_thai="IN_PROGRESS"
        ).count(),
        "reopened": tickets.filter(
            trang_thai="REOPENED"
        ).count(),
        "resolved": tickets.filter(
            trang_thai="RESOLVED"
        ).count(),
        "closed": tickets.filter(
            trang_thai="CLOSED"
        ).count(),
        "overdue": tickets.filter(
            sla_deadline__lt=now
        ).exclude(
            trang_thai__in=FINAL_TICKET_STATUSES
        ).count(),
    }

    # ==========================================
    # 2. TỔNG QUAN HỒ SƠ THẨM ĐỊNH M4
    # ==========================================

    dispute_stats = {
        "total": disputes.count(),
        "waiting": disputes.filter(
            trang_thai="CHO_TIEP_NHAN"
        ).count(),
        "processing": disputes.filter(
            trang_thai="DANG_THAM_DINH"
        ).count(),
        "supplement": disputes.filter(
            trang_thai="CHO_BO_SUNG"
        ).count(),
        "concluded": disputes.filter(
            trang_thai="DA_KET_LUAN"
        ).count(),
        "unassigned": disputes.filter(
            ma_nhan_vien_tham_dinh__isnull=True
        ).exclude(
            trang_thai="DA_KET_LUAN"
        ).count(),
    }

    # ==========================================
    # 3. TỔNG QUAN CSAT M5
    # ==========================================

    csat = CSAT.objects.aggregate(
        total=Count("pk"),
        average=Avg("score"),
    )

    csat_average = (
        round(csat["average"], 2)
        if csat["average"] is not None
        else None
    )

    # ==========================================
    # 4. THỐNG KÊ NHÂN VIÊN CSKH
    # ==========================================

    cskh_staff = list(
        Staff.objects
        .filter(vai_tro="CSKH")
        .select_related("ma_tai_khoan")
        .annotate(
            open_count=Count(
                "tickets_duoc_giao",
                filter=Q(
                    tickets_duoc_giao__trang_thai__in=(
                        OPEN_TICKET_STATUSES
                    )
                ),
            ),
            total_count=Count(
                "tickets_duoc_giao",
            ),
            closed_count=Count(
                "tickets_duoc_giao",
                filter=Q(
                    tickets_duoc_giao__trang_thai="CLOSED"
                ),
            ),
        )
        .order_by("ma_nhan_vien")
    )

    # ==========================================
    # 5. THỐNG KÊ NHÂN VIÊN THẨM ĐỊNH
    # ==========================================

    assessor_staff = list(
        Staff.objects
        .filter(vai_tro="ASSESSOR")
        .select_related("ma_tai_khoan")
        .order_by("ma_nhan_vien")
    )

    assessor_counts = {
        item["ma_nhan_vien_tham_dinh"]: item
        for item in (
            disputes.filter(
                ma_nhan_vien_tham_dinh__isnull=False
            )
            .values("ma_nhan_vien_tham_dinh")
            .annotate(
                total=Count("pk"),
                open=Count(
                    "pk",
                    filter=Q(
                        trang_thai__in=OPEN_DISPUTE_STATUSES
                    ),
                ),
                concluded=Count(
                    "pk",
                    filter=Q(
                        trang_thai="DA_KET_LUAN"
                    ),
                ),
            )
        )
    }

    for staff in assessor_staff:
        counts = assessor_counts.get(
            staff.ma_nhan_vien,
            {},
        )

        staff.dashboard_total = counts.get("total", 0)
        staff.dashboard_open = counts.get("open", 0)
        staff.dashboard_concluded = counts.get(
            "concluded",
            0,
        )

    # ==========================================
    # 6. BỘ LỌC DASHBOARD
    # ==========================================

    selected_cskh = request.GET.get(
        "cskh", ""
    ).strip()

    selected_assessor = request.GET.get(
        "assessor", ""
    ).strip()

    selected_status = request.GET.get(
        "status", ""
    ).strip()

    selected_assessment = request.GET.get(
        "assessment", ""
    ).strip()

    valid_cskh_ids = {
        str(item.ma_nhan_vien)
        for item in cskh_staff
    }

    valid_assessor_ids = {
        str(item.ma_nhan_vien)
        for item in assessor_staff
    }

    if selected_cskh not in valid_cskh_ids:
        selected_cskh = ""

    if selected_assessor not in valid_assessor_ids:
        selected_assessor = ""

    status_choices = list(
        Ticket._meta.get_field(
            "trang_thai"
        ).choices
    )

    valid_statuses = {
        value
        for value, label in status_choices
    }

    if selected_status not in valid_statuses:
        selected_status = ""

    if selected_assessment not in ("YES", "NO"):
        selected_assessment = ""

    # ==========================================
    # 7. LỌC TICKET
    # ==========================================

    filtered_tickets = Ticket.objects.select_related(
        "khach_hang",
        "nguoi_phu_trach",
        "danh_muc",
    ).order_by(
        "-thoi_diem_tao",
        "-pk",
    )

    if selected_cskh:
        filtered_tickets = filtered_tickets.filter(
            nguoi_phu_trach_id=int(selected_cskh)
        )

    if selected_status:
        filtered_tickets = filtered_tickets.filter(
            trang_thai=selected_status
        )

    # Truy vấn từ DisputeCase để tránh phụ thuộc
    # vào tên related_name của quan hệ OneToOne.

    if selected_assessor:
        related_ticket_ids = disputes.filter(
            ma_nhan_vien_tham_dinh_id=int(
                selected_assessor
            )
        ).values("ma_ticket_id")

        filtered_tickets = filtered_tickets.filter(
            pk__in=related_ticket_ids
        )

    if selected_assessment == "YES":
        related_ticket_ids = disputes.values(
            "ma_ticket_id"
        )

        filtered_tickets = filtered_tickets.filter(
            pk__in=related_ticket_ids
        )

    elif selected_assessment == "NO":
        related_ticket_ids = disputes.values(
            "ma_ticket_id"
        )

        filtered_tickets = filtered_tickets.exclude(
            pk__in=related_ticket_ids
        )

    # ==========================================
    # 8. PHÂN TRANG
    # ==========================================

    page_obj = Paginator(
        filtered_tickets,
        20,
    ).get_page(
        request.GET.get("page")
    )

    page_tickets = list(page_obj.object_list)

    ticket_ids = [
        item.pk
        for item in page_tickets
    ]

    # ==========================================
    # 9. LIÊN KẾT TICKET M3 VỚI HỒ SƠ M4
    # ==========================================

    dispute_map = {
        item.ma_ticket_id: item
        for item in (
            disputes.filter(
                ma_ticket_id__in=ticket_ids
            )
            .select_related(
                "ma_nhan_vien_tham_dinh",
                "ma_don_hang",
            )
        )
    }

    ticket_rows = [
        {
            "ticket": item,
            "dispute": dispute_map.get(item.pk),
        }
        for item in page_tickets
    ]

    # ==========================================
    # 10. THÔNG BÁO CHỜ MANAGER PHÊ DUYỆT
    # ==========================================

    # Chỉ lấy phương án:
    # - Là phương án HOAN_TIEN.
    # - Đã được gửi phê duyệt (CHO_DUYET).
    # - Chưa có quyết định của MANAGER.
    #
    # Không lấy các phương án mới DE_XUAT,
    # đã bị từ chối hoặc đã được phê duyệt.

    approval_notifications_queryset = (
        CompensationAction.objects.filter(
            loai_phuong_an="HOAN_TIEN",
            trang_thai="CHO_DUYET",
            ket_qua_phe_duyet__isnull=True,
        )
        .select_related(
            "ma_ho_so",
            "ma_ho_so__ma_ticket",
            "ma_ho_so__ma_ticket__khach_hang",
            "ma_ho_so__ma_don_hang",
            "nguoi_de_xuat",
            "ma_chi_tiet_don",
        )
        .order_by(
            "-thoi_diem_cap_nhat",
            "-ma_phuong_an",
        )
    )

    # Đếm toàn bộ số phương án cần phê duyệt.
    approval_notifications_count = (
        approval_notifications_queryset.count()
    )

    # Lấy tối đa 10 đề xuất để hiển thị trên Dashboard.
    approval_notifications = list(
        approval_notifications_queryset[:10]
    )

    # Đề xuất mới nhất sẽ xuất hiện trên popup.
    approval_notification_latest = None

    if approval_notifications:
        approval_notification_latest = (
            approval_notifications[0]
        )

    # ==========================================
    # 11. TRUYỀN DỮ LIỆU SANG TEMPLATE
    # ==========================================

    context = {
        "role": role,
        "ticket_stats": ticket_stats,
        "dispute_stats": dispute_stats,
        "csat_total": csat["total"],
        "csat_average": csat_average,
        "cskh_staff": cskh_staff,
        "assessor_staff": assessor_staff,
        "ticket_rows": ticket_rows,
        "page_obj": page_obj,
        "ticket_status_choices": status_choices,
        "selected_cskh": selected_cskh,
        "selected_assessor": selected_assessor,
        "selected_status": selected_status,
        "selected_assessment": selected_assessment,
        "query_without_page": "&".join(
            f"{key}={value}"
            for key, value in [
                ("cskh", selected_cskh),
                ("assessor", selected_assessor),
                ("status", selected_status),
                ("assessment", selected_assessment),
            ]
            if value
        ),

        # Dữ liệu mới: thông báo phương án chờ duyệt.
        "approval_notifications": (
            approval_notifications
        ),
        "approval_notifications_count": (
            approval_notifications_count
        ),
        "approval_notification_latest": (
            approval_notification_latest
        ),
    }

    return render(
        request,
        "accounts/manager_dashboard.html",
        context,
    )
