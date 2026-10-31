from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.models import Staff
from tickets.models import Ticket, TicketLog

from .models import CompensationAction, DisputeCase, Order, OrderItem


def _lay_ho_so_de_xu_ly(*, user, ma_ho_so):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied(
            "Bạn cần đăng nhập bằng tài khoản hoạt động."
        )

    nhan_vien = Staff.objects.filter(
        ma_tai_khoan=user,
        vai_tro="ASSESSOR",
    ).first()

    if nhan_vien is None:
        raise PermissionDenied(
            "Chỉ nhân viên thẩm định được thực hiện thao tác này."
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
        ma_ticket_id=ticket.pk,
        ma_nhan_vien_tham_dinh=nhan_vien,
    ).first()

    if ho_so is None:
        raise PermissionDenied(
            "Phân công hồ sơ đã thay đổi. Vui lòng tải lại trang."
        )

    return nhan_vien, ticket, ho_so


def _kiem_tra_ticket_dang_cho_tham_dinh(ticket):
    if ticket.trang_thai != "IN_PROGRESS":
        raise ValidationError("Ticket phải đang được CSKH xử lý.")

    if ticket.trang_thai_tham_dinh != "WAITING":
        raise ValidationError(
            "Ticket chưa có yêu cầu thẩm định đang chờ kết quả."
        )


def _chon_nhan_vien_tham_dinh():
    nhan_vien = (
        Staff.objects
        .filter(
            vai_tro="ASSESSOR",
            san_sang_nhan_viec=True,
            ma_tai_khoan__is_active=True,
        )
        .annotate(
            so_ho_so_dang_mo=Count(
                "ho_so_tham_dinh",
                filter=Q(
                    ho_so_tham_dinh__trang_thai__in=[
                        "CHO_TIEP_NHAN",
                        "DANG_THAM_DINH",
                        "CHO_BO_SUNG",
                    ]
                ),
            )
        )
        .order_by("so_ho_so_dang_mo", "pk")
        .first()
    )

    if nhan_vien is None:
        raise ValidationError(
            "Hiện không có nhân viên thẩm định sẵn sàng nhận hồ sơ."
        )

    return nhan_vien


@transaction.atomic
def tao_hoac_lay_ho_so(*, ticket, ma_don_hang=None):
    ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)

    if (
        ticket.trang_thai != "IN_PROGRESS"
        or ticket.trang_thai_tham_dinh != "WAITING"
    ):
        raise ValidationError(
            "Ticket phải đang xử lý và chờ kết quả thẩm định."
        )

    if ma_don_hang is not None:
        if ma_don_hang.ma_khach_hang_id != ticket.khach_hang_id:
            raise ValidationError(
                "Đơn hàng không thuộc khách hàng của Ticket."
            )

    ho_so = (
        DisputeCase.objects.select_for_update()
        .filter(ma_ticket=ticket)
        .first()
    )

    if ho_so is not None:
        cap_nhat_fields = []

        if ho_so.ma_nhan_vien_tham_dinh_id is None:
            ho_so.ma_nhan_vien_tham_dinh = (
                _chon_nhan_vien_tham_dinh()
            )
            cap_nhat_fields.append("ma_nhan_vien_tham_dinh")

        if ma_don_hang is not None:
            if ho_so.ma_don_hang_id is None:
                ho_so.ma_don_hang = ma_don_hang
                cap_nhat_fields.append("ma_don_hang")
            elif ho_so.ma_don_hang_id != ma_don_hang.pk:
                raise ValidationError(
                    "Hồ sơ đã được liên kết với đơn hàng khác."
                )

        if cap_nhat_fields:
            ho_so.full_clean()
            ho_so.save(
                update_fields=[
                    *cap_nhat_fields,
                    "thoi_diem_cap_nhat",
                ]
            )

        return ho_so

    ho_so = DisputeCase(
        ma_ticket=ticket,
        ma_nhan_vien_tham_dinh=_chon_nhan_vien_tham_dinh(),
        ma_don_hang=ma_don_hang,
    )
    ho_so.full_clean()
    ho_so.save()

    return ho_so


@transaction.atomic
def tiep_nhan_ho_so(*, user, ma_ho_so):
    nhan_vien, ticket, ho_so = _lay_ho_so_de_xu_ly(
        user=user,
        ma_ho_so=ma_ho_so,
    )

    if ho_so.trang_thai != "CHO_TIEP_NHAN":
        raise ValidationError(
            "Hồ sơ không còn ở trạng thái chờ tiếp nhận."
        )

    _kiem_tra_ticket_dang_cho_tham_dinh(ticket)

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


@transaction.atomic
def ghi_nhan_ket_luan(
    *,
    user,
    ma_ho_so,
    ket_qua_tham_dinh,
    ket_luan,
):
    nhan_vien, ticket, ho_so = _lay_ho_so_de_xu_ly(
        user=user,
        ma_ho_so=ma_ho_so,
    )

    if ho_so.trang_thai != "DANG_THAM_DINH":
        raise ValidationError(
            "Chỉ được ghi kết luận khi hồ sơ đang thẩm định."
        )

    _kiem_tra_ticket_dang_cho_tham_dinh(ticket)

    cac_ket_qua_hop_le = dict(
        DisputeCase.KET_QUA_THAM_DINH_CHOICES
    )

    if (
        not isinstance(ket_qua_tham_dinh, str)
        or ket_qua_tham_dinh not in cac_ket_qua_hop_le
    ):
        raise ValidationError(
            "Bạn cần chọn Có cơ sở hoặc Không có cơ sở."
        )

    if not isinstance(ket_luan, str) or not ket_luan.strip():
        raise ValidationError(
            "Bạn cần nhập căn cứ thẩm định."
        )

    ket_luan = ket_luan.strip()

    if ho_so.ket_luan or ho_so.ket_qua_tham_dinh:
        raise ValidationError(
            "Hồ sơ đã có kết luận. Không được ghi đè kết luận cũ."
        )

    so_ban_ghi = DisputeCase.objects.filter(
        pk=ho_so.pk,
        ma_ticket_id=ticket.pk,
        ma_nhan_vien_tham_dinh=nhan_vien,
        trang_thai="DANG_THAM_DINH",
        ket_qua_tham_dinh="",
        ket_luan="",
        ma_ticket__trang_thai="IN_PROGRESS",
        ma_ticket__trang_thai_tham_dinh="WAITING",
    ).update(
        ket_qua_tham_dinh=ket_qua_tham_dinh,
        ket_luan=ket_luan,
        trang_thai="DA_KET_LUAN",
        thoi_diem_cap_nhat=timezone.now(),
    )

    if so_ban_ghi != 1:
        raise ValidationError(
            "Hồ sơ đã thay đổi. Vui lòng tải lại trang."
        )

    ket_qua_hien_thi = cac_ket_qua_hop_le[ket_qua_tham_dinh]

    TicketLog.objects.create(
        ticket=ticket,
        nguoi_thuc_hien=user,
        hanh_dong="KET_LUAN_THAM_DINH",
        noi_dung=(
            f"Nhân viên {nhan_vien.ho_ten} ghi kết luận "
            f"hồ sơ #{ho_so.pk}.\n"
            f"Kết quả: {ket_qua_hien_thi}.\n"
            f"Căn cứ: {ket_luan}"
        ),
    )

    ho_so.refresh_from_db()
    return ho_so


@transaction.atomic
def lap_phuong_an(
    *,
    user,
    ma_ho_so,
    loai_phuong_an,
    noi_dung,
    ly_do,
    so_tien_hoan,
    phien_ban_hien_tai,
):
    nhan_vien, ticket, ho_so = _lay_ho_so_de_xu_ly(
        user=user,
        ma_ho_so=ma_ho_so,
    )

    _kiem_tra_ticket_dang_cho_tham_dinh(ticket)

    if (
        ho_so.trang_thai != "DA_KET_LUAN"
        or not ho_so.ket_luan.strip()
    ):
        raise ValidationError(
            "Hồ sơ phải có kết luận trước khi lập phương án."
        )

    if not ho_so.ma_don_hang_id:
        raise ValidationError(
            "Hồ sơ chưa được liên kết với đơn hàng."
        )

    don_hang = Order.objects.select_for_update().get(
        pk=ho_so.ma_don_hang_id
    )

    if don_hang.ma_khach_hang_id != ticket.khach_hang_id:
        raise ValidationError(
            "Đơn hàng không thuộc khách hàng của Ticket."
        )

    if loai_phuong_an not in dict(
        CompensationAction.LOAI_PHUONG_AN_MOI_CHOICES
    ):
        raise ValidationError(
            "Vui lòng chọn một trong bốn phương án trên giao diện."
        )

    if not isinstance(noi_dung, str) or not noi_dung.strip():
        raise ValidationError("Bạn cần nhập nội dung phương án.")

    if not isinstance(ly_do, str) or not ly_do.strip():
        raise ValidationError(
            "Bạn cần nhập căn cứ đề xuất hoặc lý do điều chỉnh."
        )

    try:
        so_tien = Decimal(str(so_tien_hoan))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Số tiền hoàn không hợp lệ.")

    if not so_tien.is_finite():
        raise ValidationError("Số tiền hoàn không hợp lệ.")

    if so_tien < 0:
        raise ValidationError("Số tiền hoàn không được âm.")

    if loai_phuong_an == "HOAN_TIEN":
        if so_tien <= 0:
            raise ValidationError("Số tiền hoàn phải lớn hơn 0.")

        tong_da_thanh_toan = OrderItem.objects.filter(
            ma_don_hang=don_hang
        ).aggregate(
            tong=Sum("gia_tri_da_thanh_toan")
        )["tong"] or Decimal("0")

        if so_tien > tong_da_thanh_toan:
            raise ValidationError(
                "Số tiền hoàn không được vượt tổng tiền sản phẩm "
                f"đã thanh toán: {tong_da_thanh_toan} "
                f"{don_hang.don_vi_tien_te}."
            )
    elif so_tien != 0:
        raise ValidationError(
            "Chỉ phương án hoàn tiền được nhập số tiền hoàn. "
            "Các phương án còn lại nhập 0."
        )

    if (
        isinstance(phien_ban_hien_tai, bool)
        or not isinstance(phien_ban_hien_tai, int)
        or phien_ban_hien_tai < 0
    ):
        raise ValidationError("Phiên bản phương án không hợp lệ.")

    phuong_an_cu = (
        CompensationAction.objects.select_for_update()
        .filter(ma_ho_so=ho_so)
        .order_by("-phien_ban")
        .first()
    )

    phien_ban_moi_nhat = (
        phuong_an_cu.phien_ban if phuong_an_cu else 0
    )

    if phien_ban_hien_tai != phien_ban_moi_nhat:
        raise ValidationError(
            "Phương án đã được cập nhật hoặc biểu mẫu đã được gửi. "
            "Vui lòng tải lại trang trước khi tiếp tục."
        )

    if phuong_an_cu and phuong_an_cu.trang_thai not in {
        "DE_XUAT",
        "TU_CHOI",
    }:
        raise ValidationError(
            "Chỉ được điều chỉnh phương án đang đề xuất "
            "hoặc đã bị từ chối."
        )

    phuong_an = CompensationAction(
        ma_ho_so=ho_so,
        phien_ban=phien_ban_moi_nhat + 1,
        loai_phuong_an=loai_phuong_an,
        noi_dung=noi_dung.strip(),
        ly_do=ly_do.strip(),
        so_tien_hoan=so_tien,
        don_vi_tien_te=don_hang.don_vi_tien_te,
        nguoi_de_xuat=nhan_vien,
        trang_thai="DE_XUAT",
    )

    phuong_an.full_clean()

    if phuong_an_cu:
        phuong_an_cu.trang_thai = "DA_THAY_THE"
        phuong_an_cu.save(
            update_fields=["trang_thai", "thoi_diem_cap_nhat"]
        )

    phuong_an.save()

    TicketLog.objects.create(
        ticket=ticket,
        nguoi_thuc_hien=user,
        hanh_dong="DE_XUAT_PHUONG_AN",
        noi_dung=(
            f"Hồ sơ #{ho_so.pk} - "
            f"Phương án V{phuong_an.phien_ban}.\n"
            f"Loại: {phuong_an.get_loai_phuong_an_display()}.\n"
            f"Số tiền hoàn: {phuong_an.so_tien_hoan} "
            f"{phuong_an.don_vi_tien_te}.\n"
            f"Nội dung: {phuong_an.noi_dung}\n"
            f"Căn cứ/lý do: {phuong_an.ly_do}"
        ),
    )

    return phuong_an