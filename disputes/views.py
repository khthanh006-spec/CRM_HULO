from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Staff
from accounts.permissions import role_required

from .models import DisputeCase
from .services import tiep_nhan_ho_so


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

    trang_thai_hop_le = dict(
        DisputeCase.TRANG_THAI_CHOICES
    )

    if trang_thai in trang_thai_hop_le:
        ho_so_list = ho_so_list.filter(
            trang_thai=trang_thai
        )
    else:
        trang_thai = ""

    return render(
        request,
        "disputes/home.html",
        {
            "ho_so_list": ho_so_list,
            "tu_khoa": tu_khoa,
            "trang_thai": trang_thai,
            "trang_thai_choices": (
                DisputeCase.TRANG_THAI_CHOICES
            ),
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

    tep_dinh_kem = ticket.attachments.all().order_by(
        "-thoi_diem_tai_len"
    )

    lich_su = ticket.logs.select_related(
        "nguoi_thuc_hien"
    ).order_by("-thoi_diem")

    nhan_vien = Staff.objects.filter(
        ma_tai_khoan=request.user,
        vai_tro="ASSESSOR",
    ).first()

    la_nguoi_duoc_phan_cong = (
        nhan_vien is not None
        and ho_so.ma_nhan_vien_tham_dinh_id == nhan_vien.pk
    )

    co_the_tiep_nhan = (
        la_nguoi_duoc_phan_cong
        and ho_so.trang_thai == "CHO_TIEP_NHAN"
        and ticket.trang_thai == "IN_PROGRESS"
        and ticket.trang_thai_tham_dinh == "WAITING"
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
            "tep_dinh_kem": tep_dinh_kem,
            "lich_su": lich_su,
            "co_the_tiep_nhan": co_the_tiep_nhan,
            "ly_do_chua_the_tiep_nhan": (
                ly_do_chua_the_tiep_nhan
            ),
        },
    )


@role_required("ASSESSOR")
@require_POST
def dispute_accept(request, pk):
    # Kiểm tra quyền xem trước khi thực hiện nghiệp vụ.
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
        messages.error(
            request,
            " ".join(exc.messages),
        )
    else:
        messages.success(
            request,
            f"Đã tiếp nhận hồ sơ thẩm định #{ho_so.pk}.",
        )

    return redirect(
        "disputes:detail",
        pk=pk,
    )