
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from customers.models import Customer

from .forms import YeuCauHoTroForm
from .services import (
    tao_ticket_theo_chuan_m3,
    tim_danh_muc_m3,
)
from .attachment_integration import tao_ticket_kem_bang_chung


# Anh xa 6 nhom van de M2 sang danh muc M3 dang hoat dong.
# Day la anh xa mac dinh theo nhom, chua phan loai chi tiet.
BANG_ANH_XA_M2_M3 = {
    "DON_HANG": "Sai sản phẩm / đơn hàng",
    "GIAO_HANG": "Chậm giao hàng",
    "DOI_TRA": "Đổi trả / Hoàn tiền",
    "THANH_TOAN": "Thanh toán / Hóa đơn",
    "SAN_PHAM_LOI": "Hàng bị lỗi",
    "KHAC": "Khiếu nại dịch vụ",
}


@login_required(login_url="login")
@require_POST
def gui_yeu_cau_sang_m3(request):
    """
    Gui yeu cau ho tro tu M2 sang M3.

    - Kiem tra khach hang so huu ban nhap.
    - Anh xa loai van de M2 sang danh muc M3.
    - Su dung service tao Ticket chinh thuc cua M3.
    - Ho tro yeu cau co hoac khong co anh.
    - Giu ban nhap neu luu Ticket/anh that bai.
    - Chi thong bao thanh cong khi service hoan tat.
    """

    # 1. Xac dinh khach hang
    khach_hang = Customer.objects.filter(
        ma_tai_khoan=request.user
    ).first()

    if khach_hang is None:
        return HttpResponseForbidden(
            "Tai khoan chua co ho so khach hang."
        )

    # 2. Lay ban nhap M2
    yeu_cau = request.session.get(
        "m2_yeu_cau_ho_tro"
    )

    if not isinstance(yeu_cau, dict):
        messages.error(
            request,
            "Khong tim thay yeu cau ho tro can gui."
        )
        return redirect("chatbot:chuyen_ho_tro")

    if yeu_cau.get("ma_khach_hang") != khach_hang.pk:
        return HttpResponseForbidden(
            "Ban khong co quyen gui yeu cau nay."
        )

    # 3. Kiem tra thong tin yeu cau
    thong_tin = yeu_cau.get("thong_tin")

    if not isinstance(thong_tin, dict):
        messages.error(
            request,
            "Vui long khai bao day du thong tin yeu cau."
        )
        return redirect("chatbot:khai_bao_yeu_cau")

    form = YeuCauHoTroForm(thong_tin)

    if not form.is_valid():
        messages.error(
            request,
            "Thong tin yeu cau chua hop le."
        )
        return redirect("chatbot:khai_bao_yeu_cau")

    # 4. Anh xa loai van de M2 sang danh muc M3
    try:
        danh_muc = tim_danh_muc_m3(
            loai_van_de=yeu_cau.get("loai_van_de"),
            bang_anh_xa=BANG_ANH_XA_M2_M3,
        )

    except ValueError as error:
        messages.error(
            request,
            f"Khong the xac dinh danh muc M3: {error}"
        )
        return redirect("chatbot:xac_nhan_yeu_cau")

    # 5. Kiem tra kieu du lieu bang chung
    bang_chung = yeu_cau.get("bang_chung", [])

    if not isinstance(bang_chung, list):
        messages.error(
            request,
            "Danh sach bang chung khong hop le."
        )
        return redirect("chatbot:xac_nhan_yeu_cau")

    # 6. Goi service phu hop
    try:
        if bang_chung:
            # Co anh: M2 dieu phoi Ticket + TicketAttachment
            ticket = tao_ticket_kem_bang_chung(
                yeu_cau=yeu_cau,
                khach_hang=khach_hang,
                danh_muc=danh_muc,
            )
        else:
            # Khong co anh: tao Ticket qua service M3
            ticket = tao_ticket_theo_chuan_m3(
                yeu_cau=yeu_cau,
                khach_hang=khach_hang,
                danh_muc=danh_muc,
            )

    except (ValueError, ValidationError) as error:
        # Giu nguyen ban nhap de khach hang thu lai
        messages.error(
            request,
            f"Khong the gui yeu cau: {error}"
        )
        return redirect("chatbot:xac_nhan_yeu_cau")

    # 7. Ghi nhan Ticket da tao
    request.session["m2_ticket_vua_tao"] = {
        "ticket_id": ticket.pk,
        "ma_ticket": ticket.ma_ticket,
    }

    # Chi xoa ban nhap khi service tra ve thanh cong
    request.session.pop(
        "m2_yeu_cau_ho_tro",
        None,
    )

    messages.success(
        request,
        f"Gui yeu cau thanh cong! "
        f"Ma Ticket cua ban la {ticket.ma_ticket}."
    )

    return redirect("chatbot:home")
