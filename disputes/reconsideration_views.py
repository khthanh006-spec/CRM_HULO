from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.permissions import role_required

from .reconsideration_services import tiep_nhan_xem_xet_lai
from .views import _ho_so_duoc_phep_xem, _la_nguoi_tham_dinh


class XemXetLaiForm(forms.Form):
    ma_phuong_an = forms.IntegerField(
        min_value=1,
        widget=forms.HiddenInput(),
    )

    noi_dung = forms.CharField(
        label="Nội dung cần xem xét lại",
        min_length=10,
        max_length=5000,
        strip=True,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": (
                    "Nêu vấn đề cần kiểm tra lại dựa trên "
                    "phản hồi của khách và kết quả đã thực hiện..."
                ),
            }
        ),
    )

    xac_nhan = forms.BooleanField(
        label=(
            "Tôi đã đọc phản hồi khách hàng và kết quả "
            "thực hiện phương án trước đó."
        ),
        error_messages={
            "required": "Bạn cần xác nhận đã kiểm tra thông tin.",
        },
    )


@role_required("ASSESSOR")
@require_http_methods(["GET", "POST"])
def dispute_reconsider(request, pk):
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

    phuong_an = (
        ho_so.phuong_an_xu_ly
        .select_related("nguoi_de_xuat")
        .order_by("-phien_ban")
        .first()
    )

    du_dieu_kien = (
        ticket.trang_thai == "IN_PROGRESS"
        and ticket.trang_thai_tham_dinh == "COMPLETED"
        and ticket.trang_thai_xac_nhan == "DISAGREED"
        and bool((ticket.ly_do_khong_dong_y or "").strip())
        and ticket.thoi_diem_xac_nhan is not None
        and ho_so.trang_thai == "DA_KET_LUAN"
        and bool((ho_so.ket_luan or "").strip())
        and ho_so.ma_don_hang_id is not None
        and (
            ho_so.ma_don_hang.ma_khach_hang_id
            == ticket.khach_hang_id
        )
        and phuong_an is not None
        and phuong_an.trang_thai == "DA_HOAN_TAT"
        and phuong_an.thoi_diem_hoan_tat is not None
        and ticket.thoi_diem_xac_nhan
        > phuong_an.thoi_diem_hoan_tat
    )

    if not du_dieu_kien:
        messages.error(
            request,
            "Hồ sơ chưa đủ điều kiện tiếp nhận xem xét lại. "
            "Khách phải không đồng ý với kết quả sau khi phương án "
            "hoàn tất, và CSKH phải tiếp tục xử lý Ticket mở lại.",
        )
        return redirect("disputes:detail", pk=pk)

    form = XemXetLaiForm(
        request.POST if request.method == "POST" else None,
        initial={"ma_phuong_an": phuong_an.pk},
    )

    if request.method == "POST" and form.is_valid():
        try:
            tiep_nhan_xem_xet_lai(
                user=request.user,
                ma_ho_so=pk,
                ma_phuong_an=form.cleaned_data["ma_phuong_an"],
                noi_dung=form.cleaned_data["noi_dung"],
            )
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(
                request,
                "Đã tiếp nhận xem xét lại trên hồ sơ cũ. "
                "Kết quả và phương án trước đó được giữ nguyên.",
            )
            return redirect("disputes:detail", pk=pk)

    return render(
        request,
        "disputes/dispute_reconsider.html",
        {
            "ho_so": ho_so,
            "ticket": ticket,
            "phuong_an": phuong_an,
            "form": form,
        },
    )