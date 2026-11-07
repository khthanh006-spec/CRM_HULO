
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


# ==================================================
# ÁNH XẠ LOẠI VẤN ĐỀ M2 SANG DANH MỤC M3
# ==================================================

BANG_ANH_XA_M2_M3 = {
    "DON_HANG": "Sai sản phẩm / đơn hàng",
    "GIAO_HANG": "Chậm giao hàng",
    "DOI_TRA": "Đổi trả / Hoàn tiền",
    "THANH_TOAN": "Thanh toán / Hóa đơn",
    "SAN_PHAM_LOI": "Hàng bị lỗi",
    "KHAC": "Khiếu nại dịch vụ",
}


# ==================================================
# M2 -> M3: GỬI YÊU CẦU HỖ TRỢ CHÍNH THỨC
# ==================================================

@login_required(login_url="login")
@require_POST
def gui_yeu_cau_sang_m3(request):
    """
    Gửi yêu cầu hỗ trợ từ Module 2 sang Module 3.

    Chức năng:
    - Xác định khách hàng đang đăng nhập.
    - Kiểm tra quyền sở hữu bản nháp M2.
    - Kiểm tra đơn hàng có thuộc khách hàng hay không.
    - Ánh xạ loại vấn đề M2 sang danh mục Ticket M3.
    - Tạo Ticket có hoặc không có ảnh bằng chứng.
    - Giữ bản nháp nếu gửi thất bại.
    - Chống tạo Ticket trùng thông qua source_request_id.
    """

    # --------------------------------------------------
    # 1. XÁC ĐỊNH KHÁCH HÀNG
    # --------------------------------------------------

    khach_hang = Customer.objects.filter(
        ma_tai_khoan=request.user
    ).first()

    if khach_hang is None:
        return HttpResponseForbidden(
            "Tài khoản chưa có hồ sơ khách hàng."
        )

    # --------------------------------------------------
    # 2. LẤY BẢN NHÁP M2
    # --------------------------------------------------

    yeu_cau = request.session.get(
        "m2_yeu_cau_ho_tro"
    )

    if not isinstance(yeu_cau, dict):
        messages.error(
            request,
            "Không tìm thấy yêu cầu hỗ trợ cần gửi."
        )

        return redirect(
            "chatbot:chuyen_ho_tro"
        )

    # Kiểm tra bản nháp thuộc khách hàng đang đăng nhập
    if yeu_cau.get("ma_khach_hang") != khach_hang.pk:
        return HttpResponseForbidden(
            "Bạn không có quyền gửi yêu cầu này."
        )

    # --------------------------------------------------
    # 3. KIỂM TRA THÔNG TIN YÊU CẦU
    # --------------------------------------------------

    thong_tin = yeu_cau.get("thong_tin")

    if not isinstance(thong_tin, dict):
        messages.error(
            request,
            "Vui lòng khai báo đầy đủ thông tin yêu cầu."
        )

        return redirect(
            "chatbot:khai_bao_yeu_cau"
        )

    # CẬP NHẬT QUAN TRỌNG:
    # Truyền đúng khách hàng vào Form.
    #
    # Form sẽ kiểm tra:
    # - Mã đơn hàng có tồn tại hay không.
    # - Đơn hàng có thuộc khách hàng không.
    # - Dữ liệu khai báo có hợp lệ không.
    #
    # Nếu không truyền customer, dropdown sẽ
    # không nhận diện được đơn hàng đã chọn.

    form = YeuCauHoTroForm(
        thong_tin,
        customer=khach_hang,
    )

    if not form.is_valid():

        messages.error(
            request,
            "Thông tin yêu cầu chưa hợp lệ. "
            "Vui lòng kiểm tra đơn hàng và nội dung đã nhập."
        )

        return redirect(
            "chatbot:khai_bao_yeu_cau"
        )

    # --------------------------------------------------
    # 4. ÁNH XẠ LOẠI VẤN ĐỀ M2 SANG DANH MỤC M3
    # --------------------------------------------------

    try:
        danh_muc = tim_danh_muc_m3(
            loai_van_de=yeu_cau.get(
                "loai_van_de"
            ),
            bang_anh_xa=BANG_ANH_XA_M2_M3,
        )

    except ValueError as error:

        messages.error(
            request,
            f"Không thể xác định danh mục M3: {error}"
        )

        return redirect(
            "chatbot:xac_nhan_yeu_cau"
        )

    # --------------------------------------------------
    # 5. KIỂM TRA DANH SÁCH BẰNG CHỨNG
    # --------------------------------------------------

    bang_chung = yeu_cau.get(
        "bang_chung",
        []
    )

    if not isinstance(bang_chung, list):

        messages.error(
            request,
            "Danh sách bằng chứng không hợp lệ."
        )

        return redirect(
            "chatbot:xac_nhan_yeu_cau"
        )

    # --------------------------------------------------
    # 6. GỌI SERVICE TẠO TICKET M3
    # --------------------------------------------------

    try:

        if bang_chung:

            # Có ảnh bằng chứng:
            # Tạo Ticket và chuyển ảnh sang M3.

            ticket = tao_ticket_kem_bang_chung(
                yeu_cau=yeu_cau,
                khach_hang=khach_hang,
                danh_muc=danh_muc,
            )

        else:

            # Không có ảnh:
            # Tạo Ticket qua service M3.

            ticket = tao_ticket_theo_chuan_m3(
                yeu_cau=yeu_cau,
                khach_hang=khach_hang,
                danh_muc=danh_muc,
            )

    except (ValueError, ValidationError) as error:

        # Không xóa bản nháp nếu tạo Ticket thất bại.
        messages.error(
            request,
            f"Không thể gửi yêu cầu: {error}"
        )

        return redirect(
            "chatbot:xac_nhan_yeu_cau"
        )

    # --------------------------------------------------
    # 7. GHI NHẬN TICKET ĐÃ TẠO
    # --------------------------------------------------

    request.session["m2_ticket_vua_tao"] = {
        "ticket_id": ticket.pk,
        "ma_ticket": ticket.ma_ticket,
    }

    # Chỉ xóa bản nháp sau khi service thành công.
    request.session.pop(
        "m2_yeu_cau_ho_tro",
        None,
    )

    messages.success(
        request,
        (
            "Gửi yêu cầu thành công! "
            f"Mã Ticket của bạn là {ticket.ma_ticket}."
        )
    )

    return redirect(
        "chatbot:home"
    )
