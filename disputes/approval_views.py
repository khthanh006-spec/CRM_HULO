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
        required=False,
        help_text="Bắt buộc nhập khi từ chối hoặc yêu cầu điều chỉnh.",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Nhập lý do nếu yêu cầu điều chỉnh. "
                    "Có thể để trống khi phê duyệt."
                ),
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()

        if (
            cleaned_data.get("quyet_dinh") == "TU_CHOI"
            and not cleaned_data.get("ly_do", "").strip()
        ):
            self.add_error(
                "ly_do",
                "Bạn phải nhập lý do khi từ chối hoặc yêu cầu điều chỉnh.",
            )

        return cleaned_data


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

    if phuong_an is None:
        messages.error(request, "Hồ sơ chưa có phương án xử lý.")
        return redirect("disputes:detail", pk=pk)

    if phuong_an.loai_phuong_an != "HOAN_TIEN":
        messages.info(
            request,
            "Phương án này do nhân viên thẩm định quyết định, "
            "không cần gửi quản lý.",
        )
        return redirect("disputes:detail", pk=pk)

    # Form lập phương án hiện tại đã tự gửi hoàn tiền sang CHO_DUYET.
    if phuong_an.trang_thai == "CHO_DUYET":
        messages.info(
            request,
            "Phương án hoàn tiền đã được gửi và đang chờ quản lý duyệt.",
        )
        return redirect("disputes:detail", pk=pk)

    if (
        phuong_an.trang_thai != "DE_XUAT"
        or ho_so.trang_thai != "DA_KET_LUAN"
        or not ho_so.ket_luan.strip()
        or not _ticket_dang_cho_tham_dinh(ho_so.ma_ticket)
    ):
        messages.error(
            request,
            "Hồ sơ hoặc phương án chưa đủ điều kiện gửi phê duyệt.",
        )
        return redirect("disputes:detail", pk=pk)

    loi = ""

    if request.method == "POST":
        try:
            ma_phuong_an = int(request.POST.get("ma_phuong_an", ""))
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
                    f"Đã gửi phương án hoàn tiền V{ket_qua.phien_ban} "
                    "đến quản lý.",
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
    quan_ly = Staff.objects.filter(
        ma_tai_khoan=request.user,
        vai_tro="MANAGER",
    ).first()

    if quan_ly is None or not request.user.is_active:
        raise PermissionDenied(
            "Bạn cần tài khoản nhân viên đang hoạt động có vai trò Quản lý."
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

    if phuong_an.loai_phuong_an != "HOAN_TIEN":
        messages.info(
            request,
            "Chỉ phương án hoàn tiền cần quản lý xét duyệt.",
        )
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
        and phuong_an.nguoi_de_xuat_id != quan_ly.pk
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
                ket_qua = quyet_dinh_phuong_an(
                    user=request.user,
                    ma_ho_so=pk,
                    **form.cleaned_data,
                )
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                messages.success(
                    request,
                    (
                        "Đã phê duyệt hoàn tiền. "
                        "Phương án sẵn sàng thực hiện."
                        if ket_qua.quyet_dinh == "PHE_DUYET"
                        else "Đã yêu cầu điều chỉnh. "
                        "Nhân viên thẩm định cần lập phiên bản mới."
                    ),
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