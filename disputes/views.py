from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from accounts.models import Staff
from accounts.permissions import role_required

from .models import DisputeCase


# =========================================================
# PHẠM VI HỒ SƠ ĐƯỢC PHÉP XEM
# =========================================================
def _ho_so_duoc_phep_xem(user):
    ho_so_list = DisputeCase.objects.select_related(
        "ma_ticket",
        "ma_ticket__khach_hang",
        "ma_ticket__danh_muc",
        "ma_ticket__nguoi_phu_trach",
        "ma_nhan_vien_tham_dinh",
        "ma_don_hang",
    )

    # Admin được xem toàn bộ hồ sơ.
    if user.is_superuser:
        return ho_so_list

    staff = Staff.objects.filter(
        ma_tai_khoan=user
    ).first()

    if staff is None:
        raise PermissionDenied(
            "Tài khoản chưa có hồ sơ nhân viên."
        )

    # Nhân viên thẩm định chỉ xem hồ sơ được giao.
    if staff.vai_tro == "ASSESSOR":
        return ho_so_list.filter(
            ma_nhan_vien_tham_dinh=staff
        )

    if staff.vai_tro == "MANAGER":
        return ho_so_list

    raise PermissionDenied(
        "Bạn không có quyền xem hồ sơ thẩm định."
    )


# =========================================================
# UC-4.1: DANH SÁCH HỒ SƠ
# =========================================================
@role_required("ADMIN", "ASSESSOR", "MANAGER")
def dispute_home(request):
    ho_so_list = _ho_so_duoc_phep_xem(request.user)

    tu_khoa = request.GET.get("q", "").strip()

    if tu_khoa:
        ho_so_list = ho_so_list.filter(
            Q(ma_ticket__ma_ticket__icontains=tu_khoa)
            | Q(ma_ticket__tieu_de__icontains=tu_khoa)
            | Q(ma_ticket__khach_hang__ho_ten__icontains=tu_khoa)
        )

    trang_thai = request.GET.get("trang_thai", "").strip()
    trang_thai_choices = DisputeCase.TRANG_THAI_CHOICES

    if trang_thai in dict(trang_thai_choices):
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
            "trang_thai_choices": trang_thai_choices,
        },
    )


# =========================================================
# UC-4.1: CHI TIẾT HỒ SƠ
# =========================================================
@role_required("ADMIN", "ASSESSOR", "MANAGER")
def dispute_detail(request, pk):
    ho_so_list = _ho_so_duoc_phep_xem(request.user)

    ho_so = get_object_or_404(
        ho_so_list,
        pk=pk,
    )

    ticket = ho_so.ma_ticket
    don_hang = ho_so.ma_don_hang

    # Chỉ hiển thị đơn hàng thuộc đúng khách hàng của Ticket.
    if (
        don_hang is not None
        and don_hang.ma_khach_hang_id != ticket.khach_hang_id
    ):
        raise PermissionDenied(
            "Đơn hàng liên kết không thuộc khách hàng của Ticket."
        )

    # Lấy sản phẩm của đúng đơn hàng liên kết.
    chi_tiet_don = []

    if don_hang is not None:
        chi_tiet_don = don_hang.items.select_related(
            "ma_san_pham"
        ).order_by("pk")

    tep_dinh_kem = ticket.attachments.all().order_by(
        "-thoi_diem_tai_len"
    )

    lich_su = ticket.logs.select_related(
        "nguoi_thuc_hien"
    ).order_by("-thoi_diem")

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
        },
    )