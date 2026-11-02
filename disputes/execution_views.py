from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.permissions import role_required

from .execution_services import cap_nhat_thuc_hien
from .views import _ho_so_duoc_phep_xem, _la_nguoi_tham_dinh


class ThucHienForm(forms.Form):
    ma_phuong_an = forms.IntegerField(
        min_value=1,
        widget=forms.HiddenInput(),
    )

    ket_qua_thuc_hien = forms.CharField(
        label="Tiến độ / kết quả thực hiện",
        min_length=10,
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "placeholder": (
                    "Ghi công việc đã thực hiện, kết quả và thông tin "
                    "xác nhận: mã vận đơn, mã giao dịch hoàn tiền "
                    "hoặc nội dung phản hồi từ chối hỗ trợ..."
                ),
            }
        ),
    )

    xac_nhan_hoan_tat = forms.BooleanField(
        required=False,
        label=(
            "Tôi xác nhận phương án đã được thực hiện đầy đủ "
            "và thông tin kết quả là chính xác."
        ),
    )


@role_required("ASSESSOR")
@require_http_methods(["GET", "POST"])
def dispute_execute(request, pk):
    ho_so = get_object_or_404(
        _ho_so_duoc_phep_xem(request.user),
        pk=pk,
    )

    if not _la_nguoi_tham_dinh(request.user, ho_so):
        raise PermissionDenied(
            "Bạn không được phân công thực hiện hồ sơ này."
        )

    phuong_an = (
        ho_so.phuong_an_xu_ly
        .select_related("ma_chi_tiet_don")
        .order_by("-phien_ban")
        .first()
    )

    if phuong_an is None:
        messages.error(request, "Hồ sơ chưa có phương án xử lý.")
        return redirect("disputes:detail", pk=pk)

    if phuong_an.trang_thai == "DA_HOAN_TAT":
        messages.info(
            request,
            "Phương án đã hoàn tất. Kết quả đã được trả về CSKH.",
        )
        return render(
            request,
            "disputes/dispute_execution.html",
            {
                "ho_so": ho_so,
                "phuong_an": phuong_an,
                "da_hoan_tat": True,
            },
        )

    trang_thai_cho_phep = [
        "SAN_SANG_THUC_HIEN",
        "DANG_THUC_HIEN",
    ]

    if phuong_an.loai_phuong_an == "HOAN_TIEN":
        trang_thai_cho_phep.append("DA_DUYET")

    if (
        phuong_an.trang_thai not in trang_thai_cho_phep
        or ho_so.trang_thai != "DA_KET_LUAN"
        or not ho_so.ket_luan.strip()
        or ho_so.ma_ticket.trang_thai != "IN_PROGRESS"
        or ho_so.ma_ticket.trang_thai_tham_dinh != "WAITING"
    ):
        messages.error(
            request,
            "Hồ sơ hoặc phương án chưa đủ điều kiện thực hiện.",
        )
        return redirect("disputes:detail", pk=pk)

    if phuong_an.loai_phuong_an == "HOAN_TIEN":
        from .models import ApprovalRecord

        da_duoc_duyet = ApprovalRecord.objects.filter(
            ma_phuong_an=phuong_an,
            quyet_dinh="PHE_DUYET",
            nguoi_phe_duyet__vai_tro="MANAGER",
        ).exclude(
            nguoi_phe_duyet_id=phuong_an.nguoi_de_xuat_id
        ).exists()

        if not da_duoc_duyet:
            messages.error(
                request,
                "Phương án hoàn tiền chưa được quản lý phê duyệt.",
            )
            return redirect("disputes:detail", pk=pk)

    if request.method == "POST":
        form = ThucHienForm(request.POST)
        thao_tac = request.POST.get("thao_tac", "")

        if form.is_valid():
            if thao_tac not in ["luu", "hoan_tat"]:
                form.add_error(None, "Thao tác không hợp lệ.")
            elif (
                thao_tac == "hoan_tat"
                and not form.cleaned_data["xac_nhan_hoan_tat"]
            ):
                form.add_error(
                    "xac_nhan_hoan_tat",
                    "Bạn cần tích xác nhận trước khi hoàn tất.",
                )
            else:
                try:
                    cap_nhat_thuc_hien(
                        user=request.user,
                        ma_ho_so=pk,
                        ma_phuong_an=form.cleaned_data["ma_phuong_an"],
                        ket_qua_thuc_hien=(
                            form.cleaned_data["ket_qua_thuc_hien"]
                        ),
                        hoan_tat=thao_tac == "hoan_tat",
                    )
                except ValidationError as exc:
                    form.add_error(None, " ".join(exc.messages))
                else:
                    messages.success(
                        request,
                        (
                            "Đã hoàn tất phương án và trả kết quả về CSKH."
                            if thao_tac == "hoan_tat"
                            else "Đã lưu tiến độ thực hiện."
                        ),
                    )
                    return redirect("disputes:execute", pk=pk)
    else:
        form = ThucHienForm(
            initial={
                "ma_phuong_an": phuong_an.pk,
                "ket_qua_thuc_hien": phuong_an.ket_qua_thuc_hien,
            }
        )

    return render(
        request,
        "disputes/dispute_execution.html",
        {
            "ho_so": ho_so,
            "phuong_an": phuong_an,
            "form": form,
            "da_hoan_tat": False,
        },
    )
