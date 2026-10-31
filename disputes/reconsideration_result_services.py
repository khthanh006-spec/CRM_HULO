from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from tickets.models import Ticket, TicketLog, TicketMessage

from .models import CompensationAction
from .reconsideration_models import ReconsiderationRecord
from .services import _lay_ho_so_de_xu_ly


@transaction.atomic
def ghi_nhan_ket_qua_xem_xet(
    *,
    user,
    ma_ho_so,
    ma_lan_xem_xet,
    ket_qua,
):
    nhan_vien, ticket, ho_so = _lay_ho_so_de_xu_ly(
        user=user,
        ma_ho_so=ma_ho_so,
    )

    if (
        isinstance(ma_lan_xem_xet, bool)
        or not isinstance(ma_lan_xem_xet, int)
        or ma_lan_xem_xet < 1
    ):
        raise ValidationError("Mã lần xem xét không hợp lệ.")

    if not isinstance(ket_qua, str):
        raise ValidationError("Kết quả xem xét không hợp lệ.")

    ket_qua = ket_qua.strip()

    if not 10 <= len(ket_qua) <= 5000:
        raise ValidationError(
            "Kết quả xem xét phải từ 10 đến 5.000 ký tự."
        )

    if (
        ticket.trang_thai != "IN_PROGRESS"
        or ticket.trang_thai_tham_dinh != "WAITING"
        or ticket.trang_thai_xac_nhan != "DISAGREED"
    ):
        raise ValidationError(
            "Ticket phải đang xử lý, đang chờ kết quả thẩm định "
            "và có phản hồi không đồng ý của khách hàng."
        )

    if (
        ho_so.trang_thai != "DA_KET_LUAN"
        or not (ho_so.ket_luan or "").strip()
    ):
        raise ValidationError("Hồ sơ chưa có kết luận thẩm định.")

    if (
        not ho_so.ma_don_hang_id
        or ho_so.ma_don_hang.ma_khach_hang_id
        != ticket.khach_hang_id
    ):
        raise ValidationError(
            "Đơn hàng của hồ sơ không hợp lệ."
        )

    lan_xem_xet = (
        ReconsiderationRecord.objects.select_for_update()
        .filter(
            pk=ma_lan_xem_xet,
            ma_ho_so=ho_so,
        )
        .first()
    )

    if lan_xem_xet is None:
        raise ValidationError(
            "Lần xem xét không thuộc hồ sơ này."
        )

    if (
        lan_xem_xet.trang_thai != "DANG_XEM_XET"
        or lan_xem_xet.phuong_an_moi_id is not None
    ):
        raise ValidationError(
            "Lần xem xét đã kết thúc hoặc đã lập phương án mới."
        )

    if (
        ticket.thoi_diem_xac_nhan
        != lan_xem_xet.thoi_diem_phan_hoi
        or (ticket.ly_do_khong_dong_y or "").strip()
        != lan_xem_xet.ly_do_khach_hang.strip()
    ):
        raise ValidationError(
            "Phản hồi khách hàng đã thay đổi. Vui lòng tải lại trang."
        )

    phuong_an = (
        CompensationAction.objects.select_for_update()
        .filter(ma_ho_so=ho_so)
        .order_by("-phien_ban")
        .first()
    )

    if (
        phuong_an is None
        or phuong_an.pk != lan_xem_xet.phuong_an_truoc_id
        or phuong_an.trang_thai != "DA_HOAN_TAT"
        or phuong_an.thoi_diem_hoan_tat is None
    ):
        raise ValidationError(
            "Phương án hiện tại đã thay đổi hoặc chưa hoàn tất."
        )

    now = timezone.now()

    lan_xem_xet.ket_qua_xem_xet = ket_qua
    lan_xem_xet.nguoi_ket_thuc = nhan_vien
    lan_xem_xet.thoi_diem_ket_thuc = now
    lan_xem_xet.trang_thai = "DA_KET_THUC"
    lan_xem_xet.full_clean()

    # Cập nhật có điều kiện để tránh lưu kết quả trên Ticket đã đổi.
    so_ban_ghi = Ticket.objects.filter(
        pk=ticket.pk,
        trang_thai="IN_PROGRESS",
        trang_thai_tham_dinh="WAITING",
        trang_thai_xac_nhan="DISAGREED",
        thoi_diem_xac_nhan=lan_xem_xet.thoi_diem_phan_hoi,
    ).update(
        trang_thai_tham_dinh="COMPLETED",
        thoi_diem_cap_nhat=now,
    )

    if so_ban_ghi != 1:
        raise ValidationError(
            "Ticket đã thay đổi. Vui lòng tải lại trang."
        )

    lan_xem_xet.save(
        update_fields=[
            "ket_qua_xem_xet",
            "nguoi_ket_thuc",
            "thoi_diem_ket_thuc",
            "trang_thai",
        ]
    )

    noi_dung_ghi_nhan = (
        f"Kết quả xem xét lại hồ sơ #{ho_so.pk}, "
        f"lần #{lan_xem_xet.pk}.\n"
        f"Phương án liên quan: V{phuong_an.phien_ban}.\n"
        f"{ket_qua}\n"
        "Không phát sinh phương án hoặc lần thực hiện mới. "
        "CSKH tiếp tục xử lý và thông báo kết quả cho khách hàng."
    )

    TicketMessage.objects.create(
        ticket=ticket,
        nguoi_gui=user,
        loai_tin_nhan="INTERNAL",
        noi_dung=noi_dung_ghi_nhan,
    )

    TicketLog.objects.create(
        ticket=ticket,
        nguoi_thuc_hien=user,
        hanh_dong="KET_QUA_XEM_XET_LAI",
        noi_dung=(
            f"Nhân viên {nhan_vien.ho_ten} ghi nhận:\n"
            f"{noi_dung_ghi_nhan}\n"
            "Theo dõi thẩm định: WAITING → COMPLETED."
        ),
    )

    return lan_xem_xet