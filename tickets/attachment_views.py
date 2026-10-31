
"""
MODULE 3 - TICKET ATTACHMENT VIEWS

Chức năng:
- Xem trực tiếp ảnh bằng chứng.
- Tải ảnh bằng chứng về máy.
- Kiểm tra quyền truy cập trước khi mở file.

Phân quyền:
- Customer: Chỉ xem Ticket của mình.
- CSKH: Ticket được giao hoặc NEW chưa phân công.
- MANAGER: Được xem.
- Superuser: Được xem.
- ASSESSOR: Chưa cấp quyền tự động.
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

from customers.models import Customer

from .models import TicketAttachment


def _lay_bang_chung_co_quyen(request, pk):
    """
    Lấy bằng chứng và kiểm tra quyền truy cập.
    Dùng chung cho View và Download.
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

    staff = getattr(
        user,
        "staff_profile",
        None,
    )

    if user.is_superuser:
        duoc_phep = True

    elif staff is not None and staff.vai_tro == "MANAGER":
        duoc_phep = True

    elif staff is not None and staff.vai_tro == "CSKH":

        ticket_moi = (
            ticket.trang_thai == "NEW"
            and ticket.nguoi_phu_trach_id is None
        )

        ticket_duoc_giao = (
            ticket.nguoi_phu_trach_id == staff.pk
        )

        duoc_phep = (
            ticket_moi or ticket_duoc_giao
        )

    else:
        duoc_phep = Customer.objects.filter(
            ma_tai_khoan=user,
            pk=ticket.khach_hang_id,
        ).exists()

    if not duoc_phep:
        return None

    return bang_chung


def _tra_file_bang_chung(bang_chung, tai_xuong):
    """
    Mở file từ storage riêng của M3.

    tai_xuong=False: Xem trực tiếp.
    tai_xuong=True: Tải file.
    """

    if not bang_chung.tep_dinh_kem.name:
        raise Http404(
            "Tệp bằng chứng không tồn tại."
        )

    try:
        tep = bang_chung.tep_dinh_kem.open("rb")

    except (FileNotFoundError, OSError):
        raise Http404(
            "Tệp bằng chứng không tồn tại."
        )

    ten_tep = (
        Path(
            bang_chung.ten_tep_goc.replace("\\", "/")
        ).name
        if bang_chung.ten_tep_goc
        else "bang_chung.jpg"
    )

    response = FileResponse(
        tep,
        content_type="image/jpeg",
        as_attachment=tai_xuong,
        filename=ten_tep,
    )

    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"

    return response


@login_required(login_url="login")
@require_GET
def ticket_attachment_view(request, pk):
    """
    Xem ảnh trực tiếp sau khi kiểm tra quyền.
    """

    bang_chung = _lay_bang_chung_co_quyen(
        request,
        pk,
    )

    if bang_chung is None:
        return HttpResponseForbidden(
            "Bạn không có quyền xem bằng chứng này."
        )

    return _tra_file_bang_chung(
        bang_chung,
        tai_xuong=False,
    )


@login_required(login_url="login")
@require_GET
def ticket_attachment_download(request, pk):
    """
    Tải ảnh về máy sau khi kiểm tra quyền.
    """

    bang_chung = _lay_bang_chung_co_quyen(
        request,
        pk,
    )

    if bang_chung is None:
        return HttpResponseForbidden(
            "Bạn không có quyền tải bằng chứng này."
        )

    return _tra_file_bang_chung(
        bang_chung,
        tai_xuong=True,
    )
