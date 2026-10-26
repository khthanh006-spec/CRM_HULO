from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.models import Staff
from accounts.permissions import role_required

from .approval_services import (
    gui_phuong_an_phe_duyet,
    quyet_dinh_phuong_an,
)
from .models import ApprovalRecord
from .views import (
    _ho_so_duoc_phep_xem,
    _la_nguoi_tham_dinh,
    _ticket_dang_cho_tham_dinh,
)


class PheDuyetForm(forms.Form):
    ma_phuong_an = forms.IntegerField(
        min_value=1,
        widget=forms.HiddenInput(),
    )

    quyet_dinh = forms.ChoiceField(
        label="Quyết định",
        choices=[
            ("", "---------"),
            *ApprovalRecord.QUYET_DINH_CHOICES,
        ],
    )

    ly_do = forms.CharField(
        label="Nhận xét / lý do",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Nhập căn cứ phê duyệt hoặc nội dung cần điều chỉnh..."
                ),
            }
        ),
    )


@role_required("ASSESSOR")
@require_http_methods(["GET", "POST"])
def dispute_submit(request, pk):
    ho_so = get_object_or_404(
        _ho_so_duoc_phep_xem(request.user),
        pk=pk,
    )

    if not _la_nguoi_tham_dinh(request.user, ho_so):
        raise PermissionDenied(
            "Bạn không được phân công thẩm định hồ sơ này."
        )

    phuong_an = (
        ho_so.phuong_an_xu_ly
        .select_related("nguoi_de_xuat")
        .order_by("-phien_ban")
        .first()
    )

    if (
        phuong_an is None
        or phuong_an.trang_thai != "DE_XUAT"
        or ho_so.trang_thai != "DA_KET_LUAN"
        or not ho_so.ket_luan.strip()
        or not _ticket_dang_cho_tham_dinh(ho_so.ma_ticket)
    ):
        messages.error(
            request,
            "Hồ sơ chưa đủ điều kiện gửi phê duyệt "
            "hoặc phương án đã được gửi.",
        )
        return redirect("disputes:detail", pk=pk)

    loi = ""

    if request.method == "POST":
        try:
            ma_phuong_an = int(
                request.POST.get("ma_phuong_an", "")
            )
        except (TypeError, ValueError):
            loi = "Phương án không hợp lệ. Vui lòng tải lại trang."
        else:
            try:
                ket_qua = gui_phuong_an_phe_duyet(
                    user=request.user,
                    ma_ho_so=pk,
                    ma_phuong_an=ma_phuong_an,
                )
            except ValidationError as exc:
                loi = " ".join(exc.messages)
            else:
                messages.success(
                    request,
                    f"Đã gửi phương án V{ket_qua.phien_ban} "
                    "đến quản lý. Phương án đang chờ phê duyệt.",
                )
                return redirect("disputes:detail", pk=pk)

    return render(
        request,
        "disputes/dispute_submit.html",
        {
            "ho_so": ho_so,
            "phuong_an": phuong_an,
            "loi": loi,
        },
    )


@role_required("MANAGER")
@require_http_methods(["GET", "POST"])
def dispute_review(request, pk):
    if not Staff.objects.filter(
        ma_tai_khoan=request.user,
        vai_tro="MANAGER",
    ).exists():
        raise PermissionDenied(
            "Bạn cần tài khoản nhân viên có vai trò Quản lý."
        )

    ho_so = get_object_or_404(
        _ho_so_duoc_phep_xem(request.user),
        pk=pk,
    )

    phuong_an = (
        ho_so.phuong_an_xu_ly
        .select_related("nguoi_de_xuat")
        .order_by("-phien_ban")
        .first()
    )

    if phuong_an is None:
        messages.error(request, "Hồ sơ chưa có phương án xử lý.")
        return redirect("disputes:detail", pk=pk)

    ket_qua = (
        ApprovalRecord.objects
        .select_related("nguoi_phe_duyet")
        .filter(ma_phuong_an=phuong_an)
        .first()
    )

    co_the_duyet = (
        phuong_an.trang_thai == "CHO_DUYET"
        and ket_qua is None
        and ho_so.trang_thai == "DA_KET_LUAN"
        and bool(ho_so.ket_luan.strip())
        and _ticket_dang_cho_tham_dinh(ho_so.ma_ticket)
    )

    form = PheDuyetForm(
        initial={"ma_phuong_an": phuong_an.pk}
    )

    if request.method == "POST":
        if not co_the_duyet:
            messages.error(
                request,
                "Phương án không còn đủ điều kiện quyết định.",
            )
            return redirect("disputes:review", pk=pk)

        form = PheDuyetForm(request.POST)

        if form.is_valid():
            try:
                quyet_dinh_phuong_an(
                    user=request.user,
                    ma_ho_so=pk,
                    **form.cleaned_data,
                )
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                messages.success(
                    request,
                    "Đã lưu quyết định của quản lý.",
                )
                return redirect("disputes:review", pk=pk)

    return render(
        request,
        "disputes/dispute_review.html",
        {
            "ho_so": ho_so,
            "phuong_an": phuong_an,
            "ket_qua": ket_qua,
            "co_the_duyet": co_the_duyet,
            "form": form,
        },
    )