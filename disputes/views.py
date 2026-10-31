from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import Staff
from accounts.permissions import role_required

from .models import ApprovalRecord, DisputeCase
from .services import ghi_nhan_ket_luan, tiep_nhan_ho_so


def _ho_so_duoc_phep_xem(user):
    queryset = DisputeCase.objects.select_related(
        "ma_ticket",
        "ma_ticket__khach_hang",
        "ma_ticket__danh_muc",
        "ma_ticket__nguoi_phu_trach",
        "ma_nhan_vien_tham_dinh",
        "ma_don_hang",
    )

    if user.is_superuser:
        return queryset

    nhan_vien = Staff.objects.filter(
        ma_tai_khoan=user
    ).first()

    if nhan_vien is None:
        raise PermissionDenied(
            "Bạn không có quyền truy cập hồ sơ thẩm định."
        )

    if nhan_vien.vai_tro == "ASSESSOR":
        return queryset.filter(
            ma_nhan_vien_tham_dinh=nhan_vien
        )

    if nhan_vien.vai_tro == "MANAGER":
        return queryset

    raise PermissionDenied(
        "Bạn không có quyền truy cập hồ sơ thẩm định."
    )


def _la_nguoi_tham_dinh(user, ho_so):
    return Staff.objects.filter(
        pk=ho_so.ma_nhan_vien_tham_dinh_id,
        ma_tai_khoan=user,
        vai_tro="ASSESSOR",
    ).exists()


def _ticket_dang_cho_tham_dinh(ticket):
    return (
        ticket.trang_thai == "IN_PROGRESS"
        and ticket.trang_thai_tham_dinh == "WAITING"
    )


def _du_dieu_kien_lap_phuong_an(user, ho_so, phuong_an):
    from .plan_permissions import du_dieu_kien_lap_phuong_an

    return du_dieu_kien_lap_phuong_an(
        user,
        ho_so,
        phuong_an,
    )


@role_required("ADMIN", "ASSESSOR", "MANAGER")
def dispute_home(request):
    ho_so_list = _ho_so_duoc_phep_xem(request.user)

    tu_khoa = request.GET.get("q", "").strip()
    trang_thai = request.GET.get("trang_thai", "").strip()

    if tu_khoa:
        ho_so_list = ho_so_list.filter(
            Q(ma_ticket__ma_ticket__icontains=tu_khoa)
            | Q(ma_ticket__tieu_de__icontains=tu_khoa)
            | Q(ma_ticket__khach_hang__ho_ten__icontains=tu_khoa)
        )

    if trang_thai in dict(DisputeCase.TRANG_THAI_CHOICES):
        ho_so_list = ho_so_list.filter(trang_thai=trang_thai)
    else:
        trang_thai = ""

    return render(
        request,
        "disputes/home.html",
        {
            "ho_so_list": ho_so_list,
            "tu_khoa": tu_khoa,
            "trang_thai": trang_thai,
            "trang_thai_choices": DisputeCase.TRANG_THAI_CHOICES,
        },
    )


@role_required("ADMIN", "ASSESSOR", "MANAGER")
def dispute_detail(request, pk):
    ho_so = get_object_or_404(
        _ho_so_duoc_phep_xem(request.user),
        pk=pk,
    )

    ticket = ho_so.ma_ticket
    don_hang = ho_so.ma_don_hang

    if (
        don_hang is not None
        and don_hang.ma_khach_hang_id != ticket.khach_hang_id
    ):
        raise PermissionDenied(
            "Đơn hàng không thuộc khách hàng của Ticket."
        )

    chi_tiet_don = []

    if don_hang is not None:
        chi_tiet_don = (
            don_hang.items
            .select_related("ma_san_pham")
            .order_by("pk")
        )

    la_nguoi_duoc_phan_cong = (
        request.user.is_active
        and _la_nguoi_tham_dinh(request.user, ho_so)
    )

    ticket_dang_cho = _ticket_dang_cho_tham_dinh(ticket)

    da_ket_luan = (
        ho_so.trang_thai == "DA_KET_LUAN"
        and bool(ho_so.ket_luan.strip())
    )

    co_the_tiep_nhan = (
        la_nguoi_duoc_phan_cong
        and ho_so.trang_thai == "CHO_TIEP_NHAN"
        and ticket_dang_cho
    )

    co_the_ket_luan = (
        la_nguoi_duoc_phan_cong
        and ho_so.trang_thai == "DANG_THAM_DINH"
        and not ho_so.ket_luan
        and not ho_so.ket_qua_tham_dinh
        and ticket_dang_cho
    )

    phuong_an = (
        ho_so.phuong_an_xu_ly
        .select_related("nguoi_de_xuat", "ma_chi_tiet_don")
        .order_by("-phien_ban")
        .first()
    )

    ket_qua_phe_duyet = None
    co_the_xet_duyet = False
    co_the_xem_phe_duyet = False
    co_the_thuc_hien = False
    co_the_gui_phe_duyet = False

    quan_ly = Staff.objects.filter(
        ma_tai_khoan=request.user,
        vai_tro="MANAGER",
    ).first()

    if phuong_an is not None:
        la_hoan_tien = phuong_an.loai_phuong_an == "HOAN_TIEN"

        if la_hoan_tien:
            ket_qua_phe_duyet = (
                ApprovalRecord.objects
                .select_related("nguoi_phe_duyet")
                .filter(ma_phuong_an=phuong_an)
                .first()
            )

        co_the_xem_phe_duyet = (
            request.user.is_active
            and quan_ly is not None
            and la_hoan_tien
        )

        co_the_xet_duyet = (
            co_the_xem_phe_duyet
            and phuong_an.nguoi_de_xuat_id != quan_ly.pk
            and phuong_an.trang_thai == "CHO_DUYET"
            and ket_qua_phe_duyet is None
            and da_ket_luan
            and ticket_dang_cho
        )

        co_the_gui_phe_duyet = (
            la_nguoi_duoc_phan_cong
            and la_hoan_tien
            and phuong_an.trang_thai == "DE_XUAT"
            and ket_qua_phe_duyet is None
            and da_ket_luan
            and ticket_dang_cho
        )

        trang_thai_thuc_hien = {
            "SAN_SANG_THUC_HIEN",
            "DANG_THUC_HIEN",
        }

        if la_hoan_tien:
            trang_thai_thuc_hien.add("DA_DUYET")

        duoc_phep_theo_loai = phuong_an.loai_phuong_an in {
            "DOI_HANG",
            "GIAO_BO_SUNG",
            "TU_CHOI_HO_TRO",
        }

        if la_hoan_tien:
            duoc_phep_theo_loai = (
                ket_qua_phe_duyet is not None
                and ket_qua_phe_duyet.quyet_dinh == "PHE_DUYET"
                and ket_qua_phe_duyet.nguoi_phe_duyet.vai_tro == "MANAGER"
                and ket_qua_phe_duyet.nguoi_phe_duyet_id
                != phuong_an.nguoi_de_xuat_id
            )

        co_the_thuc_hien = (
            la_nguoi_duoc_phan_cong
            and da_ket_luan
            and ticket_dang_cho
            and don_hang is not None
            and phuong_an.trang_thai in trang_thai_thuc_hien
            and duoc_phep_theo_loai
        )

    from .reconsideration_context import tao_context_xem_xet_lai

    context_xem_xet = tao_context_xem_xet_lai(
        user=request.user,
        ho_so=ho_so,
        phuong_an=phuong_an,
    )

    ly_do_chua_the_tiep_nhan = ""

    if (
        la_nguoi_duoc_phan_cong
        and ho_so.trang_thai == "CHO_TIEP_NHAN"
    ):
        if ticket.trang_thai != "IN_PROGRESS":
            ly_do_chua_the_tiep_nhan = (
                "Ticket chưa ở trạng thái đang xử lý. "
                "CSKH cần tiếp nhận Ticket trước."
            )
        elif ticket.trang_thai_tham_dinh != "WAITING":
            ly_do_chua_the_tiep_nhan = (
                "Ticket chưa có yêu cầu thẩm định "
                "đang chờ kết quả từ CSKH."
            )

    return render(
        request,
        "disputes/dispute_detail.html",
        {
            "ho_so": ho_so,
            "ticket": ticket,
            "don_hang": don_hang,
            "chi_tiet_don": chi_tiet_don,
            "tep_dinh_kem": ticket.attachments.all().order_by(
                "-thoi_diem_tai_len"
            ),
            "lich_su": ticket.logs.select_related(
                "nguoi_thuc_hien"
            ).order_by("-thoi_diem"),
            "co_the_tiep_nhan": co_the_tiep_nhan,
            "co_the_ket_luan": co_the_ket_luan,
            "ly_do_chua_the_tiep_nhan": ly_do_chua_the_tiep_nhan,
            "phuong_an_moi_nhat": phuong_an,
            "co_the_lap_phuong_an": _du_dieu_kien_lap_phuong_an(
                request.user,
                ho_so,
                phuong_an,
            ),
            "ket_qua_phe_duyet": ket_qua_phe_duyet,
            "co_the_xet_duyet": co_the_xet_duyet,
            "co_the_xem_phe_duyet": co_the_xem_phe_duyet,
            "co_the_thuc_hien": co_the_thuc_hien,
            "co_the_gui_phe_duyet": co_the_gui_phe_duyet,
            **context_xem_xet,
        },
    )


@role_required("ASSESSOR")
@require_POST
def dispute_accept(request, pk):
    get_object_or_404(
        _ho_so_duoc_phep_xem(request.user),
        pk=pk,
    )

    try:
        ho_so = tiep_nhan_ho_so(
            user=request.user,
            ma_ho_so=pk,
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(
            request,
            f"Đã tiếp nhận hồ sơ thẩm định #{ho_so.pk}.",
        )

    return redirect("disputes:detail", pk=pk)


@role_required("ASSESSOR")
@require_http_methods(["GET", "POST"])
def dispute_conclusion(request, pk):
    ho_so = get_object_or_404(
        _ho_so_duoc_phep_xem(request.user),
        pk=pk,
    )

    if not _la_nguoi_tham_dinh(request.user, ho_so):
        raise PermissionDenied(
            "Bạn không được phân công thẩm định hồ sơ này."
        )

    ticket = ho_so.ma_ticket

    if (
        ho_so.trang_thai != "DANG_THAM_DINH"
        or ho_so.ket_luan
        or ho_so.ket_qua_tham_dinh
        or not _ticket_dang_cho_tham_dinh(ticket)
    ):
        messages.error(
            request,
            "Hồ sơ chưa đủ điều kiện ghi kết luận hoặc đã có kết luận.",
        )
        return redirect("disputes:detail", pk=pk)

    ket_qua_tham_dinh = ""
    ket_luan = ""
    loi = ""

    if request.method == "POST":
        ket_qua_tham_dinh = request.POST.get(
            "ket_qua_tham_dinh",
            "",
        )
        ket_luan = request.POST.get("ket_luan", "")

        try:
            ghi_nhan_ket_luan(
                user=request.user,
                ma_ho_so=pk,
                ket_qua_tham_dinh=ket_qua_tham_dinh,
                ket_luan=ket_luan,
            )
        except ValidationError as exc:
            loi = " ".join(exc.messages)
        else:
            messages.success(
                request,
                f"Đã lưu kết luận thẩm định hồ sơ #{pk}.",
            )
            return redirect("disputes:detail", pk=pk)

    return render(
        request,
        "disputes/dispute_conclusion.html",
        {
            "ho_so": ho_so,
            "ticket": ticket,
            "ket_qua_tham_dinh": ket_qua_tham_dinh,
            "ket_qua_tham_dinh_choices": (
                DisputeCase.KET_QUA_THAM_DINH_CHOICES
            ),
            "ket_luan": ket_luan,
            "loi": loi,
        },
    )


@role_required("ASSESSOR")
@require_http_methods(["GET", "POST"])
def dispute_plan(request, pk):
    from .plan_views import dispute_plan as plan_view

    return plan_view(request, pk)