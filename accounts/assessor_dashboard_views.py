
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from accounts.models import Staff
from accounts.permissions import role_required

from disputes.models import DisputeCase
from disputes.views import _ho_so_duoc_phep_xem


@role_required("ASSESSOR")
def assessor_dashboard(request):
    """
    Dashboard công việc cá nhân của nhân viên thẩm định.

    Chỉ lấy hồ sơ được phân công cho nhân viên
    đang đăng nhập, dựa trên logic phân quyền
    hiện có của hệ thống.
    """

    # ==========================================
    # 1. XÁC ĐỊNH NHÂN VIÊN THẨM ĐỊNH
    # ==========================================

    staff = Staff.objects.filter(
        ma_tai_khoan=request.user,
        vai_tro="ASSESSOR",
    ).first()

    if staff is None:
        raise PermissionDenied(
            "Không tìm thấy hồ sơ nhân viên thẩm định."
        )

    # ==========================================
    # 2. DANH SÁCH HỒ SƠ ĐƯỢC PHÉP XEM
    # ==========================================

    my_cases = (
        _ho_so_duoc_phep_xem(request.user)
        .filter(
            ma_nhan_vien_tham_dinh=staff
        )
    )

    # ==========================================
    # 3. THỐNG KÊ CÔNG VIỆC
    # ==========================================

    stats = {
        "total": my_cases.count(),

        "waiting": my_cases.filter(
            trang_thai="CHO_TIEP_NHAN"
        ).count(),

        "processing": my_cases.filter(
            trang_thai="DANG_THAM_DINH"
        ).count(),

        "supplement": my_cases.filter(
            trang_thai="CHO_BO_SUNG"
        ).count(),

        "concluded": my_cases.filter(
            trang_thai="DA_KET_LUAN"
        ).count(),
    }

    # ==========================================
    # 4. HỒ SƠ CẦN ƯU TIÊN XỬ LÝ
    # ==========================================

    priority_cases = list(
        my_cases.filter(
            trang_thai__in=[
                "CHO_TIEP_NHAN",
                "DANG_THAM_DINH",
                "CHO_BO_SUNG",
            ]
        )
        .order_by(
            "thoi_diem_tao",
            "pk",
        )[:8]
    )

    # ==========================================
    # 5. HỒ SƠ ĐƯỢC CẬP NHẬT GẦN ĐÂY
    # ==========================================

    recent_cases = list(
        my_cases.order_by(
            "-thoi_diem_cap_nhat",
            "-pk",
        )[:6]
    )

    # ==========================================
    # 6. PHƯƠNG ÁN ĐANG CHỜ PHÊ DUYỆT
    # ==========================================

    # Lấy phương án mới nhất của từng hồ sơ.
    # Không tính các phiên bản cũ đã bị thay thế.

    waiting_approval_count = 0

    for case in my_cases.prefetch_related(
        "phuong_an_xu_ly"
    ):
        latest_plan = (
            case.phuong_an_xu_ly
            .order_by("-phien_ban", "-pk")
            .first()
        )

        if (
            latest_plan is not None
            and latest_plan.loai_phuong_an == "HOAN_TIEN"
            and latest_plan.trang_thai == "CHO_DUYET"
        ):
            waiting_approval_count += 1

    # ==========================================
    # 7. CONTEXT
    # ==========================================

    context = {
        "staff": staff,
        "stats": stats,
        "priority_cases": priority_cases,
        "recent_cases": recent_cases,
        "waiting_approval_count": (
            waiting_approval_count
        ),
    }

    return render(
        request,
        "accounts/assessor_dashboard.html",
        context,
    )
