from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.permissions import role_required

from .models import CompensationAction, OrderItem
from .plan_services import luu_phuong_an_theo_bpmn
from .views import (
    _du_dieu_kien_lap_phuong_an,
    _ho_so_duoc_phep_xem,
    _la_nguoi_tham_dinh,
)


class PhuongAnBPMNForm(forms.Form):
    loai_phuong_an = forms.ChoiceField(
        label="Loại phương án",
        choices=CompensationAction.LOAI_PHUONG_AN_MOI_CHOICES,
    )

    ma_chi_tiet_don = forms.ModelChoiceField(
        label="Sản phẩm trong đơn",
        queryset=OrderItem.objects.none(),
        required=False,
        empty_label="Chọn sản phẩm liên quan",
    )

    so_luong = forms.IntegerField(
        label="Số lượng xử lý / khiếu nại",
        min_value=1,
        required=False,
    )

    dia_chi_nhan = forms.CharField(
        label="Địa chỉ nhận hàng",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    so_tien_hoan = forms.DecimalField(
        label="Số tiền đề xuất hoàn",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(
            attrs={"step": "0.01", "min": "0"}
        ),
    )

    ly_do_tu_choi = forms.CharField(
        label="Lý do từ chối hỗ trợ",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    noi_dung = forms.CharField(
        label="Nội dung phương án",
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    ly_do = forms.CharField(
        label="Căn cứ đề xuất / lý do điều chỉnh",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    phien_ban_hien_tai = forms.IntegerField(
        min_value=0,
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, ho_so, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["ma_chi_tiet_don"].queryset = (
            OrderItem.objects
            .filter(ma_don_hang_id=ho_so.ma_don_hang_id)
            .select_related("ma_don_hang", "ma_san_pham")
            .order_by("pk")
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
            "Hồ sơ hoặc phương án hiện tại "
            "không đủ điều kiện lập/điều chỉnh phương án.",
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
        loai = {
            "GUI_LAI_HANG": "DOI_HANG",
            "KHONG_BOI_THUONG": "TU_CHOI_HO_TRO",
        }.get(
            phuong_an_moi_nhat.loai_phuong_an,
            phuong_an_moi_nhat.loai_phuong_an,
        )

        # Mã "Phương án khác" cũ cần chọn lại rõ loại.
        if loai == "PHUONG_AN_KHAC":
            loai = ""

        initial.update({
            "loai_phuong_an": loai,
            "noi_dung": phuong_an_moi_nhat.noi_dung,
            "so_tien_hoan": phuong_an_moi_nhat.so_tien_hoan,
            "ma_chi_tiet_don": phuong_an_moi_nhat.ma_chi_tiet_don_id,
            "so_luong": phuong_an_moi_nhat.so_luong,
            "dia_chi_nhan": phuong_an_moi_nhat.dia_chi_nhan,
            "ly_do_tu_choi": phuong_an_moi_nhat.ly_do_tu_choi,
        })

    if request.method == "POST":
        form = PhuongAnBPMNForm(
            request.POST,
            ho_so=ho_so,
        )

        if form.is_valid():
            du_lieu = form.cleaned_data.copy()
            chi_tiet = du_lieu["ma_chi_tiet_don"]

            du_lieu["ma_chi_tiet_don"] = (
                chi_tiet.pk if chi_tiet else None
            )

            du_lieu["so_tien_hoan"] = (
                du_lieu["so_tien_hoan"] or 0
            )

            try:
                phuong_an = luu_phuong_an_theo_bpmn(
                    user=request.user,
                    ma_ho_so=pk,
                    **du_lieu,
                )
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                messages.success(
                    request,
                    f"Đã lưu phương án V{phuong_an.phien_ban}: "
                    f"{phuong_an.get_trang_thai_display()}.",
                )
                return redirect("disputes:detail", pk=pk)
    else:
        form = PhuongAnBPMNForm(
            initial=initial,
            ho_so=ho_so,
        )

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
