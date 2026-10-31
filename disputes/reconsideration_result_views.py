from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.permissions import role_required

from .reconsideration_models import ReconsiderationRecord
from .reconsideration_result_services import ghi_nhan_ket_qua_xem_xet
from .views import _ho_so_duoc_phep_xem, _la_nguoi_tham_dinh


class KetQuaXemXetForm(forms.Form):
    ma_lan_xem_xet = forms.IntegerField(
        min_value=1,
        widget=forms.HiddenInput(),
    )

    ket_qua = forms.CharField(
        label="Kết quả kiểm tra và hướng xử lý",
        min_length=10,
        max_length=5000,
        strip=True,
        widget=forms.Textarea(
            attrs={
                "rows": 7,
                "placeholder": (
                    "Nêu thông tin đã kiểm tra, kết quả xác minh "
                    "và nội dung cần bàn giao cho CSKH..."
                ),
            }
        ),
    )

    xac_nhan = forms.BooleanField(
        label=(
            "Việc xem xét đã đủ kết quả để bàn giao cho CSKH "
            "và không phát sinh phương án thực hiện mới."
        ),
        error_messages={
            "required": "Bạn cần xác nhận trước khi lưu kết quả.",
        },
    )


@role_required("ASSESSOR")
@require_http_methods(["GET", "POST"])
def dispute_reconsider_result(request, pk):
    ho_so = get_object_or_404(
        _ho_so_duoc_phep_xem(request.user),
        pk=pk,
    )

    if (
        not request.user.is_active
        or not _la_nguoi_tham_dinh(request.user, ho_so)
    ):
        raise PermissionDenied(
            "Bạn không được phân công thẩm định hồ sơ này."
        )

    ticket = ho_so.ma_ticket

    lan_xem_xet = (
        ReconsiderationRecord.objects
        .select_related("phuong_an_truoc", "nguoi_ket_thuc")
        .filter(ma_ho_so=ho_so)
        .order_by("-thoi_diem_tao", "-pk")
        .first()
    )

    if lan_xem_xet is None:
        messages.error(
            request,
            "Bạn cần tiếp nhận xem xét lại trước.",
        )
        return redirect("disputes:detail", pk=pk)

    da_ket_thuc = lan_xem_xet.trang_thai == "DA_KET_THUC"

    if not da_ket_thuc and (
        lan_xem_xet.trang_thai != "DANG_XEM_XET"
        or ticket.trang_thai != "IN_PROGRESS"
        or ticket.trang_thai_tham_dinh != "WAITING"
        or ticket.trang_thai_xac_nhan != "DISAGREED"
        or ticket.thoi_diem_xac_nhan
        != lan_xem_xet.thoi_diem_phan_hoi
    ):
        messages.error(
            request,
            "Lần xem xét hiện tại không đủ điều kiện ghi kết quả.",
        )
        return redirect("disputes:detail", pk=pk)

    if da_ket_thuc and request.method == "POST":
        messages.error(
            request,
            "Kết quả đã được lưu, không được ghi đè.",
        )
        return redirect("disputes:reconsider_result", pk=pk)

    form = KetQuaXemXetForm(
        request.POST if request.method == "POST" else None,
        initial={"ma_lan_xem_xet": lan_xem_xet.pk},
    )

    if request.method == "POST" and form.is_valid():
        # Không cho biểu mẫu cũ ghi kết quả cho lần xem xét khác.
        if form.cleaned_data["ma_lan_xem_xet"] != lan_xem_xet.pk:
            form.add_error(
                None,
                "Lần xem xét đã thay đổi. Vui lòng tải lại trang.",
            )
        else:
            try:
                ghi_nhan_ket_qua_xem_xet(
                    user=request.user,
                    ma_ho_so=pk,
                    ma_lan_xem_xet=lan_xem_xet.pk,
                    ket_qua=form.cleaned_data["ket_qua"],
                )
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                messages.success(
                    request,
                    "Đã ghi nhận kết quả xem xét và bàn giao cho CSKH.",
                )
                return redirect("disputes:reconsider_result", pk=pk)

    return render(
        request,
        "disputes/dispute_reconsider_result.html",
        {
            "ho_so": ho_so,
            "ticket": ticket,
            "lan_xem_xet": lan_xem_xet,
            "da_ket_thuc": da_ket_thuc,
            "form": form,
        },
    )