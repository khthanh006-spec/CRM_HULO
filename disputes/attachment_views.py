from pathlib import PurePosixPath

from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from accounts.permissions import role_required

from .views import _ho_so_duoc_phep_xem


def _lay_tep_duoc_phep_xem(request, pk, attachment_pk):
    if not request.user.is_active:
        raise PermissionDenied("Tài khoản không còn hoạt động.")

    ho_so = get_object_or_404(
        _ho_so_duoc_phep_xem(request.user),
        pk=pk,
    )

    tep = get_object_or_404(
        ho_so.ma_ticket.attachments.all(),
        pk=attachment_pk,
    )

    if not tep.tep_dinh_kem or not tep.tep_dinh_kem.name:
        raise Http404("Tệp chưa có nội dung.")

    return tep


def _ten_tep(tep):
    ten = (
        tep.ten_tep_goc
        or PurePosixPath(tep.tep_dinh_kem.name).name
    )

    ten = PurePosixPath(ten.replace("\\", "/")).name

    return (
        ten.replace("\r", "").replace("\n", "")
        or f"bang-chung-{tep.pk}"
    )


def _mo_tep(tep):
    try:
        return tep.tep_dinh_kem.open("rb")
    except FileNotFoundError as exc:
        raise Http404(
            "Không tìm thấy nội dung tệp trong kho lưu trữ."
        ) from exc


def _nhan_dien_anh(header):
    # Nhận diện theo nội dung đầu tệp, không chỉ theo tên.
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"

    if (
        header.startswith(b"RIFF")
        and header[8:12] == b"WEBP"
    ):
        return "image/webp"

    return None


@role_required("ADMIN", "ASSESSOR", "MANAGER")
@require_safe
@never_cache
def dispute_attachment_preview(request, pk, attachment_pk):
    tep = _lay_tep_duoc_phep_xem(
        request,
        pk,
        attachment_pk,
    )

    noi_dung = _mo_tep(tep)

    try:
        header = noi_dung.read(16)
        noi_dung.seek(0)
        loai_anh = _nhan_dien_anh(header)
    except Exception:
        noi_dung.close()
        raise

    if loai_anh is None:
        noi_dung.close()
        return HttpResponse(
            "Tệp này không hỗ trợ xem ảnh trực tiếp. "
            "Bạn có thể dùng chức năng tải tệp.",
            status=415,
            content_type="text/plain; charset=utf-8",
        )

    response = FileResponse(
        noi_dung,
        as_attachment=False,
        filename=_ten_tep(tep),
        content_type=loai_anh,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cross-Origin-Resource-Policy"] = "same-origin"

    return response


@role_required("ADMIN", "ASSESSOR", "MANAGER")
@require_safe
@never_cache
def dispute_attachment_download(request, pk, attachment_pk):
    tep = _lay_tep_duoc_phep_xem(
        request,
        pk,
        attachment_pk,
    )

    response = FileResponse(
        _mo_tep(tep),
        as_attachment=True,
        filename=_ten_tep(tep),
        content_type="application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"

    return response