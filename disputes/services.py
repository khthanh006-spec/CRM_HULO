from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import Staff
from tickets.models import Ticket, TicketLog

from .models import DisputeCase


@transaction.atomic
def tiep_nhan_ho_so(*, user, ma_ho_so):
    """
    Tiếp nhận hồ sơ thẩm định được phân công.
    Giữ nguyên trạng thái và nhân viên CSKH của Ticket.
    """

    if not user.is_authenticated:
        raise PermissionDenied("Bạn cần đăng nhập.")

    nhan_vien = Staff.objects.filter(
        ma_tai_khoan=user,
        vai_tro="ASSESSOR",
    ).first()

    if nhan_vien is None:
        raise PermissionDenied(
            "Chỉ nhân viên thẩm định được tiếp nhận hồ sơ."
        )

    thong_tin = DisputeCase.objects.filter(
        pk=ma_ho_so,
        ma_nhan_vien_tham_dinh=nhan_vien,
    ).values("ma_ticket_id").first()

    if thong_tin is None:
        raise PermissionDenied(
            "Hồ sơ không tồn tại hoặc không được phân công cho bạn."
        )

    ticket = Ticket.objects.select_for_update().get(
        pk=thong_tin["ma_ticket_id"]
    )

    ho_so = DisputeCase.objects.select_for_update().filter(
        pk=ma_ho_so,
        ma_nhan_vien_tham_dinh=nhan_vien,
        ma_ticket_id=ticket.pk,
    ).first()

    if ho_so is None:
        raise PermissionDenied(
            "Phân công hồ sơ đã thay đổi. Vui lòng tải lại trang."
        )

    if ho_so.trang_thai != "CHO_TIEP_NHAN":
        raise ValidationError(
            "Hồ sơ không còn ở trạng thái chờ tiếp nhận."
        )

    if ticket.trang_thai != "IN_PROGRESS":
        raise ValidationError(
            "Ticket phải đang được CSKH xử lý trước khi "
            "tiếp nhận thẩm định."
        )

    if ticket.trang_thai_tham_dinh != "WAITING":
        raise ValidationError(
            "Ticket chưa có yêu cầu thẩm định đang chờ kết quả."
        )

    so_ban_ghi = DisputeCase.objects.filter(
        pk=ho_so.pk,
        ma_ticket_id=ticket.pk,
        ma_nhan_vien_tham_dinh=nhan_vien,
        trang_thai="CHO_TIEP_NHAN",
        ma_ticket__trang_thai="IN_PROGRESS",
        ma_ticket__trang_thai_tham_dinh="WAITING",
    ).update(
        trang_thai="DANG_THAM_DINH",
        thoi_diem_cap_nhat=timezone.now(),
    )

    if so_ban_ghi != 1:
        raise ValidationError(
            "Trạng thái hoặc phân công đã thay đổi. "
            "Vui lòng tải lại trang."
        )

    TicketLog.objects.create(
        ticket=ticket,
        nguoi_thuc_hien=user,
        hanh_dong="TIEP_NHAN_THAM_DINH",
        noi_dung=(
            f"Nhân viên {nhan_vien.ho_ten} tiếp nhận "
            f"hồ sơ thẩm định #{ho_so.pk}."
        ),
    )

    ho_so.refresh_from_db()

    return ho_so