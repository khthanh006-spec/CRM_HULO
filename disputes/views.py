from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import Staff
from accounts.permissions import role_required

from .models import CompensationAction, DisputeCase
from .services import (
    ghi_nhan_ket_luan,
    lap_phuong_an,
    tiep_nhan_ho_so,
)


class PhuongAnForm(forms.Form):
    loai_phuong_an = forms.ChoiceField(
        label="Loại phương án",
        choices=CompensationAction.LOAI_PHUONG_AN_MOI_CHOICES,
    )

    so_tien_hoan = forms.DecimalField(
        label="Số tiền đề xuất hoàn",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(
            attrs={
                "step": "0.01",
                "min": "0",
            }
        ),
        help_text=(
            "Chỉ nhập số tiền khi chọn Hoàn tiền. "
            "Các phương án còn lại nhập 0."
        ),
    )

    noi_dung = forms.CharField(
        label="Nội dung phương án",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Mô tả cụ thể phương án xử lý...",
            }
        ),
    )

    ly_do = forms.CharField(
        label="Căn cứ đề xuất hoặc lý do điều chỉnh",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": (
                    "Nêu căn cứ từ kết luận, đơn hàng và bằng chứng..."
                ),
            }
        ),
    )

    phien_ban_hien_tai = forms.IntegerField(
        min_value=0,
        widget=forms.HiddenInput(),
    )


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
    return (
        _la_nguoi_tham_dinh(user, ho_so)
        and ho_so.trang_thai == "DA_KET_LUAN"
        and bool(ho_so.ket_luan.strip())
        and _ticket_dang_cho_tham_dinh(ho_so.ma_ticket)
        and ho_so.ma_don_hang_id is not None
        and (
            ho_so.ma_don_hang.ma_khach_hang_id
            == ho_so.ma_ticket.khach_hang_id
        )
        and (
            phuong_an is None
            or phuong_an.trang_thai in {"DE_XUAT", "TU_CHOI"}
        )
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

    la_nguoi_duoc_phan_cong = _la_nguoi_tham_dinh(
        request.user,
        ho_so,
    )

    co_the_tiep_nhan = (
        la_nguoi_duoc_phan_cong
        and ho_so.trang_thai == "CHO_TIEP_NHAN"
        and _ticket_dang_cho_tham_dinh(ticket)
    )

    co_the_ket_luan = (
        la_nguoi_duoc_phan_cong
        and ho_so.trang_thai == "DANG_THAM_DINH"
        and not ho_so.ket_luan
        and _ticket_dang_cho_tham_dinh(ticket)
    )

    phuong_an_moi_nhat = (
        ho_so.phuong_an_xu_ly
        .select_related("nguoi_de_xuat")
        .order_by("-phien_ban")
        .first()
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
            "phuong_an_moi_nhat": phuong_an_moi_nhat,
            "co_the_lap_phuong_an": _du_dieu_kien_lap_phuong_an(
                request.user,
                ho_so,
                phuong_an_moi_nhat,
            ),
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
        or not _ticket_dang_cho_tham_dinh(ticket)
    ):
        messages.error(
            request,
            "Hồ sơ chưa đủ điều kiện ghi kết luận "
            "hoặc đã có kết luận.",
        )
        return redirect("disputes:detail", pk=pk)

    ket_luan = ""
    loi = ""

    if request.method == "POST":
        ket_luan = request.POST.get("ket_luan", "")

        try:
            ghi_nhan_ket_luan(
                user=request.user,
                ma_ho_so=pk,
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
            "ket_luan": ket_luan,
            "loi": loi,
        },
    )


@role_required("ASSESSOR")
@require_http_methods(["GET", "POST"])
def dispute_plan(request, pk):
    ho_so = get_object_or_404(
        _ho_so_duoc_phep_xem(request.user),
        pk=pk,
    )

    if not _la_nguoi_tham_dinh(request.user, ho_so):
        raise PermissionDenied(
            "Bạn không được phân công thẩm định hồ sơ này."
        )

    phuong_an_moi_nhat = (
        ho_so.phuong_an_xu_ly
        .order_by("-phien_ban")
        .first()
    )

    if not _du_dieu_kien_lap_phuong_an(
        request.user,
        ho_so,
        phuong_an_moi_nhat,
    ):
        messages.error(
            request,
            "Hồ sơ chưa đủ điều kiện lập phương án "
            "hoặc phương án hiện tại không được phép điều chỉnh.",
        )
        return redirect("disputes:detail", pk=pk)

    initial = {
        "phien_ban_hien_tai": (
            phuong_an_moi_nhat.phien_ban
            if phuong_an_moi_nhat else 0
        ),
        "so_tien_hoan": 0,
    }

    if phuong_an_moi_nhat:
        # Chuyển lựa chọn cũ sang ô tương ứng khi điều chỉnh.
        loai_phuong_an = {
            "GUI_LAI_HANG": "DOI_HANG",
            "KHONG_BOI_THUONG": "PHUONG_AN_KHAC",
        }.get(
            phuong_an_moi_nhat.loai_phuong_an,
            phuong_an_moi_nhat.loai_phuong_an,
        )

        initial.update(
            {
                "loai_phuong_an": loai_phuong_an,
                "so_tien_hoan": phuong_an_moi_nhat.so_tien_hoan,
                "noi_dung": phuong_an_moi_nhat.noi_dung,
            }
        )

    if request.method == "POST":
        form = PhuongAnForm(request.POST)

        if form.is_valid():
            try:
                phuong_an = lap_phuong_an(
                    user=request.user,
                    ma_ho_so=pk,
                    **form.cleaned_data,
                )
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                messages.success(
                    request,
                    f"Đã lưu phương án V{phuong_an.phien_ban} "
                    f"cho hồ sơ #{pk}.",
                )
                return redirect("disputes:detail", pk=pk)
    else:
        form = PhuongAnForm(initial=initial)

    return render(
        request,
        "disputes/dispute_plan.html",
        {
            "ho_so": ho_so,
            "ticket": ho_so.ma_ticket,
            "don_hang": ho_so.ma_don_hang,
            "form": form,
            "phuong_an_moi_nhat": phuong_an_moi_nhat,
            "lich_su_phuong_an": (
                ho_so.phuong_an_xu_ly
                .select_related("nguoi_de_xuat")
                .order_by("-phien_ban")
            ),
        },
    )