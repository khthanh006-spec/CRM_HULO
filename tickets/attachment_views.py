
"""
TICKET ATTACHMENT VIEWS - HULOECOM

Chức năng:
- Xem ảnh minh chứng JPG, JPEG, PNG.
- Tải ảnh hoặc tài liệu PDF.
- Kiểm tra quyền truy cập trước khi mở tệp.

Phân quyền:
- CUSTOMER: Chỉ tệp thuộc Ticket của mình.
- CSKH: Ticket được giao hoặc NEW chưa phân công.
- MANAGER: Được xem toàn bộ minh chứng.
- ADMIN: Không truy cập qua chức năng nghiệp vụ.
- ASSESSOR: Chưa cấp quyền qua endpoint này.
"""

from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import (
    FileResponse,
    HttpResponseForbidden,
    Http404,
)
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from accounts.permissions import get_user_role
from customers.models import Customer

from .models import TicketAttachment


CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
}


def _lay_bang_chung_co_quyen(request, pk):
    """
    Lấy tệp minh chứng và kiểm tra quyền truy cập.

    Dùng chung cho xem và tải tệp.
    """

    bang_chung = get_object_or_404(
        TicketAttachment.objects.select_related(
            "ticket",
            "ticket__khach_hang",
            "ticket__nguoi_phu_trach",
        ),
        pk=pk,
    )

    ticket = bang_chung.ticket
    user = request.user

    role = get_user_role(user)

    # ADMIN không truy cập endpoint nghiệp vụ.
    if role == "ADMIN":
        return None

    # MANAGER được xem toàn bộ minh chứng.
    if role == "MANAGER":
        return bang_chung

    # CSKH chỉ xem Ticket thuộc quyền xử lý.
    if role == "CSKH":

        staff = getattr(
            user,
            "staff_profile",
            None,
        )

        if staff is None or staff.vai_tro != "CSKH":
            return None

        ticket_moi = (
            ticket.trang_thai == "NEW"
            and ticket.nguoi_phu_trach_id is None
        )

        ticket_duoc_giao = (
            ticket.nguoi_phu_trach_id == staff.pk
        )

        if ticket_moi or ticket_duoc_giao:
            return bang_chung

        return None

    # CUSTOMER chỉ xem Ticket của chính mình.
    if role == "CUSTOMER":

        la_chu_ticket = Customer.objects.filter(
            ma_tai_khoan=user,
            pk=ticket.khach_hang_id,
        ).exists()

        if la_chu_ticket:
            return bang_chung

        return None

    # Các vai trò khác chưa được cấp quyền.
    return None


def _tra_file_bang_chung(bang_chung, tai_xuong):
    """
    Trả về tệp từ storage.

    - Ảnh JPG, JPEG, PNG có thể xem trực tiếp.
    - PDF được tải xuống.
    - Không phục vụ định dạng ngoài danh sách hỗ trợ.
    """

    file_field = bang_chung.tep_dinh_kem

    if not file_field.name:
        raise Http404(
            "Tệp minh chứng không tồn tại."
        )

    ten_tep = (
        Path(
            bang_chung.ten_tep_goc.replace("\\", "/")
        ).name
        if bang_chung.ten_tep_goc
        else Path(file_field.name).name
    )

    phan_mo_rong = Path(
        file_field.name
    ).suffix.lower()

    content_type = CONTENT_TYPES.get(
        phan_mo_rong
    )

    if content_type is None:
        raise Http404(
            "Định dạng tệp chưa được hỗ trợ."
        )

    # PDF tải xuống thay vì hiển thị trực tiếp.
    download = (
        tai_xuong
        or phan_mo_rong == ".pdf"
    )

    try:
        tep = file_field.open("rb")

    except (FileNotFoundError, OSError):
        raise Http404(
            "Tệp minh chứng không tồn tại."
        )

    response = FileResponse(
        tep,
        content_type=content_type,
        as_attachment=download,
        filename=ten_tep,
    )

    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"

    return response


@login_required(login_url="login")
@require_GET
def ticket_attachment_view(request, pk):
    """
    Xem ảnh minh chứng sau khi kiểm tra quyền.
    PDF sẽ được tải xuống.
    """

    bang_chung = _lay_bang_chung_co_quyen(
        request,
        pk,
    )

    if bang_chung is None:
        return HttpResponseForbidden(
            "Bạn không có quyền xem minh chứng này."
        )

    return _tra_file_bang_chung(
        bang_chung,
        tai_xuong=False,
    )


@login_required(login_url="login")
@require_GET
def ticket_attachment_download(request, pk):
    """
    Tải tệp minh chứng sau khi kiểm tra quyền.
    """

    bang_chung = _lay_bang_chung_co_quyen(
        request,
        pk,
    )

    if bang_chung is None:
        return HttpResponseForbidden(
            "Bạn không có quyền tải minh chứng này."
        )

    return _tra_file_bang_chung(
        bang_chung,
        tai_xuong=True,
    )
