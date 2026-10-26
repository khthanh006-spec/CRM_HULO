
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from customers.models import Customer
from tickets.models import TicketCategory

from .forms import YeuCauHoTroForm
from .services import tao_ticket_theo_chuan_m3
from .attachment_integration import tao_ticket_kem_bang_chung


@login_required(login_url="login")
@require_POST
def gui_yeu_cau_sang_m3(request):
    """
    Gui yeu cau ho tro tu M2 sang M3.

    - Kiem tra khach hang so huu ban nhap.
    - Su dung service tao Ticket chinh thuc cua M3.
    - Ho tro yeu cau co hoac khong co anh.
    - Giu ban nhap neu luu Ticket/anh that bai.
    - Chi thong bao thanh cong khi xu ly het anh.
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

    # 4. Chi tich hop loai SAN_PHAM_LOI
    if yeu_cau.get("loai_van_de") != "SAN_PHAM_LOI":
        messages.error(
            request,
            "Loai van de nay chua duoc cau hinh tich hop M3."
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

    # 6. Anh xa danh muc M2 -> M3
    danh_muc = TicketCategory.objects.filter(
        ten_danh_muc="Hàng bị lỗi",
        dang_hoat_dong=True
    ).first()

    if danh_muc is None:
        messages.error(
            request,
            "Chua tim thay danh muc Hang bi loi cua M3."
        )
        return redirect("chatbot:xac_nhan_yeu_cau")

    # 7. Goi service phu hop
    try:
        if bang_chung:
            # Co anh: M2 dieu phoi Ticket + TicketAttachment
            ticket = tao_ticket_kem_bang_chung(
                yeu_cau=yeu_cau,
                khach_hang=khach_hang,
                danh_muc=danh_muc
            )
        else:
            # Khong co anh: giu nguyen luong M2 -> M3
            ticket = tao_ticket_theo_chuan_m3(
                yeu_cau=yeu_cau,
                khach_hang=khach_hang,
                danh_muc=danh_muc
            )

    except (ValueError, ValidationError) as error:
        # Giu nguyen ban nhap de khach hang thu lai
        messages.error(
            request,
            f"Khong the gui yeu cau: {error}"
        )
        return redirect("chatbot:xac_nhan_yeu_cau")

    # 8. Chi ghi nhan thanh cong khi service tra ve Ticket
    request.session["m2_ticket_vua_tao"] = {
        "ticket_id": ticket.pk,
        "ma_ticket": ticket.ma_ticket
    }

    # Xoa ban nhap chi sau khi xu ly thanh cong
    request.session.pop(
        "m2_yeu_cau_ho_tro",
        None
    )

    messages.success(
        request,
        f"Gui yeu cau thanh cong! "
        f"Ma Ticket cua ban la {ticket.ma_ticket}."
    )

    return redirect("chatbot:home")
