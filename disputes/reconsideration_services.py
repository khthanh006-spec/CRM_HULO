from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from tickets.models import Ticket, TicketLog

from .models import CompensationAction
from .reconsideration_models import ReconsiderationRecord
from .services import _lay_ho_so_de_xu_ly


@transaction.atomic
def tiep_nhan_xem_xet_lai(
    *,
    user,
    ma_ho_so,
    ma_phuong_an,
    noi_dung,
):
    """
    Tiếp nhận xem xét lại sau phản hồi không đồng ý.

    - Dùng lại hồ sơ cũ.
    - Lưu bản chụp phản hồi của khách hàng.
    - Chặn tiếp nhận trùng cùng một phản hồi.
    - Giữ nguyên phương án và kết quả đã thực hiện.
    - Chỉ chuyển theo dõi thẩm định COMPLETED -> WAITING.
    """
    nhan_vien, ticket, ho_so = _lay_ho_so_de_xu_ly(
        user=user,
        ma_ho_so=ma_ho_so,
    )

    if ticket.trang_thai != "IN_PROGRESS":
        raise ValidationError(
            "CSKH cần tiếp tục xử lý Ticket mở lại "
            "trước khi bộ phận thẩm định xem xét lại."
        )

    if ticket.trang_thai_xac_nhan != "DISAGREED":
        raise ValidationError(
            "Ticket chưa có phản hồi không đồng ý của khách hàng."
        )

    ly_do_khach_hang = (
        ticket.ly_do_khong_dong_y or ""
    ).strip()

    if not ly_do_khach_hang:
        raise ValidationError(
            "Chưa có lý do không đồng ý của khách hàng."
        )

    thoi_diem_phan_hoi = ticket.thoi_diem_xac_nhan

    if thoi_diem_phan_hoi is None:
        raise ValidationError(
            "Chưa ghi nhận thời điểm phản hồi của khách hàng."
        )

    if ReconsiderationRecord.objects.filter(
        ma_ho_so=ho_so,
        thoi_diem_phan_hoi=thoi_diem_phan_hoi,
    ).exists():
        raise ValidationError(
            "Phản hồi này đã được tiếp nhận xem xét lại."
        )

    if ReconsiderationRecord.objects.filter(
        ma_ho_so=ho_so,
        trang_thai="DANG_XEM_XET",
    ).exists():
        raise ValidationError(
            "Hồ sơ đang có một lần xem xét lại chưa lập phương án."
        )

    if ticket.trang_thai_tham_dinh != "COMPLETED":
        raise ValidationError(
            "Chỉ tiếp nhận xem xét lại khi lần thẩm định trước "
            "đã có kết quả và chưa có yêu cầu đang chờ."
        )

    if (
        ho_so.trang_thai != "DA_KET_LUAN"
        or not (ho_so.ket_luan or "").strip()
    ):
        raise ValidationError(
            "Hồ sơ chưa có kết luận thẩm định trước đó."
        )

    if (
        not ho_so.ma_don_hang_id
        or ho_so.ma_don_hang.ma_khach_hang_id
        != ticket.khach_hang_id
    ):
        raise ValidationError(
            "Hồ sơ cần liên kết đúng đơn hàng của khách hàng."
        )

    if (
        isinstance(ma_phuong_an, bool)
        or not isinstance(ma_phuong_an, int)
    ):
        raise ValidationError("Mã phương án không hợp lệ.")

    phuong_an = (
        CompensationAction.objects.select_for_update()
        .filter(ma_ho_so=ho_so)
        .order_by("-phien_ban")
        .first()
    )

    if phuong_an is None or phuong_an.pk != ma_phuong_an:
        raise ValidationError(
            "Phương án đã thay đổi. Vui lòng tải lại trang."
        )

    if (
        phuong_an.trang_thai != "DA_HOAN_TAT"
        or phuong_an.thoi_diem_hoan_tat is None
    ):
        raise ValidationError(
            "Chức năng này dành cho phương án đã hoàn tất."
        )

    if thoi_diem_phan_hoi <= phuong_an.thoi_diem_hoan_tat:
        raise ValidationError(
            "Phản hồi của khách hàng phải được ghi nhận "
            "sau khi phương án hiện tại hoàn tất."
        )

    if not isinstance(noi_dung, str):
        raise ValidationError(
            "Nội dung xem xét lại không hợp lệ."
        )

    noi_dung = noi_dung.strip()

    if not 10 <= len(noi_dung) <= 5000:
        raise ValidationError(
            "Nội dung tiếp nhận xem xét lại "
            "phải từ 10 đến 5.000 ký tự."
        )

    lan_xem_xet = ReconsiderationRecord(
        ma_ho_so=ho_so,
        phuong_an_truoc=phuong_an,
        nguoi_tiep_nhan=nhan_vien,
        thoi_diem_phan_hoi=thoi_diem_phan_hoi,
        ly_do_khach_hang=ly_do_khach_hang,
        noi_dung_tiep_nhan=noi_dung,
        trang_thai="DANG_XEM_XET",
    )

    lan_xem_xet.full_clean()

    now = timezone.now()

    so_ban_ghi = Ticket.objects.filter(
        pk=ticket.pk,
        trang_thai="IN_PROGRESS",
        trang_thai_tham_dinh="COMPLETED",
        trang_thai_xac_nhan="DISAGREED",
        thoi_diem_xac_nhan=thoi_diem_phan_hoi,
    ).update(
        trang_thai_tham_dinh="WAITING",
        thoi_diem_cap_nhat=now,
    )

    if so_ban_ghi != 1:
        raise ValidationError(
            "Ticket đã thay đổi hoặc yêu cầu đã được tiếp nhận. "
            "Vui lòng tải lại trang."
        )

    lan_xem_xet.save()

    TicketLog.objects.create(
        ticket=ticket,
        nguoi_thuc_hien=user,
        hanh_dong="TIEP_NHAN_XEM_XET_LAI",
        noi_dung=(
            f"Nhân viên {nhan_vien.ho_ten} tiếp nhận xem xét lại "
            f"hồ sơ #{ho_so.pk}.\n"
            f"Mã lần xem xét: {lan_xem_xet.pk}.\n"
            f"Phương án trước: V{phuong_an.phien_ban} "
            f"(mã {phuong_an.pk}), đã hoàn tất.\n"
            f"Phản hồi khách hàng lúc: "
            f"{thoi_diem_phan_hoi.isoformat()}.\n"
            f"Lý do khách không đồng ý: {ly_do_khach_hang}\n"
            f"Nội dung tiếp nhận: {noi_dung}\n"
            "Theo dõi thẩm định: COMPLETED → WAITING.\n"
            "Giữ nguyên phương án và kết quả thực hiện trước đó."
        ),
    )

    ho_so.refresh_from_db()
    return ho_so