from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import Staff
from tickets.models import Ticket, TicketLog

from .models import ApprovalRecord, CompensationAction, DisputeCase
from .services import (
    _kiem_tra_ticket_dang_cho_tham_dinh,
    _lay_ho_so_de_xu_ly,
)


def _kiem_tra_ho_so_da_ket_luan(ho_so):
    if (
        ho_so.trang_thai != "DA_KET_LUAN"
        or not ho_so.ket_luan.strip()
    ):
        raise ValidationError(
            "Hồ sơ phải có kết luận trước khi xét duyệt phương án."
        )


@transaction.atomic
def gui_phuong_an_phe_duyet(*, user, ma_ho_so, ma_phuong_an):
    """Gửi phiên bản hoàn tiền mới nhất đến quản lý."""

    nhan_vien, ticket, ho_so = _lay_ho_so_de_xu_ly(
        user=user,
        ma_ho_so=ma_ho_so,
    )

    _kiem_tra_ticket_dang_cho_tham_dinh(ticket)
    _kiem_tra_ho_so_da_ket_luan(ho_so)

    phuong_an = (
        CompensationAction.objects.select_for_update()
        .filter(ma_ho_so=ho_so)
        .order_by("-phien_ban")
        .first()
    )

    if phuong_an is None or phuong_an.pk != ma_phuong_an:
        raise ValidationError(
            "Phương án không tồn tại hoặc đã có phiên bản mới."
        )

    if phuong_an.loai_phuong_an != "HOAN_TIEN":
        raise ValidationError(
            "Chỉ phương án hoàn tiền cần quản lý phê duyệt."
        )

    if phuong_an.trang_thai != "DE_XUAT":
        raise ValidationError(
            "Phương án đã được gửi hoặc không còn ở trạng thái Đã đề xuất."
        )

    if ApprovalRecord.objects.filter(
        ma_phuong_an=phuong_an
    ).exists():
        raise ValidationError(
            "Phiên bản này đã có quyết định. Cần lập phiên bản điều chỉnh."
        )

    phuong_an.full_clean()

    so_ban_ghi = CompensationAction.objects.filter(
        pk=phuong_an.pk,
        loai_phuong_an="HOAN_TIEN",
        trang_thai="DE_XUAT",
    ).update(
        trang_thai="CHO_DUYET",
        thoi_diem_cap_nhat=timezone.now(),
    )

    if so_ban_ghi != 1:
        raise ValidationError(
            "Trạng thái phương án đã thay đổi. Vui lòng tải lại trang."
        )

    TicketLog.objects.create(
        ticket=ticket,
        nguoi_thuc_hien=user,
        hanh_dong="GUI_PHE_DUYET",
        noi_dung=(
            f"Nhân viên {nhan_vien.ho_ten} gửi phương án "
            f"hoàn tiền V{phuong_an.phien_ban}, "
            f"hồ sơ #{ho_so.pk} đến quản lý.\n"
            f"Số tiền: {phuong_an.so_tien_hoan} "
            f"{phuong_an.don_vi_tien_te}."
        ),
    )

    phuong_an.refresh_from_db()
    return phuong_an


@transaction.atomic
def quyet_dinh_phuong_an(
    *,
    user,
    ma_ho_so,
    ma_phuong_an,
    quyet_dinh,
    ly_do="",
):
    """Quản lý quyết định đối với phiên bản hoàn tiền đang chờ duyệt."""

    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied(
            "Bạn cần đăng nhập bằng tài khoản đang hoạt động."
        )

    quan_ly = Staff.objects.filter(
        ma_tai_khoan=user,
        vai_tro="MANAGER",
    ).first()

    if quan_ly is None:
        raise PermissionDenied(
            "Chỉ nhân viên có vai trò Quản lý được phê duyệt hoàn tiền."
        )

    if quyet_dinh not in dict(ApprovalRecord.QUYET_DINH_CHOICES):
        raise ValidationError("Quyết định không hợp lệ.")

    if not isinstance(ly_do, str):
        raise ValidationError("Nhận xét / lý do không hợp lệ.")

    ly_do = ly_do.strip()

    if quyet_dinh == "TU_CHOI" and not ly_do:
        raise ValidationError(
            "Bạn phải nhập lý do khi từ chối hoặc yêu cầu điều chỉnh."
        )

    thong_tin = DisputeCase.objects.filter(
        pk=ma_ho_so
    ).values("ma_ticket_id").first()

    if thong_tin is None:
        raise ValidationError("Hồ sơ không tồn tại.")

    # Thứ tự khóa thống nhất với các nghiệp vụ Module 4.
    ticket = Ticket.objects.select_for_update().get(
        pk=thong_tin["ma_ticket_id"]
    )

    ho_so = DisputeCase.objects.select_for_update().get(
        pk=ma_ho_so,
        ma_ticket_id=ticket.pk,
    )

    _kiem_tra_ticket_dang_cho_tham_dinh(ticket)
    _kiem_tra_ho_so_da_ket_luan(ho_so)

    phuong_an = (
        CompensationAction.objects.select_for_update()
        .filter(ma_ho_so=ho_so)
        .order_by("-phien_ban")
        .first()
    )

    if phuong_an is None or phuong_an.pk != ma_phuong_an:
        raise ValidationError(
            "Phiên bản phương án đã thay đổi. Vui lòng tải lại trang."
        )

    if phuong_an.loai_phuong_an != "HOAN_TIEN":
        raise ValidationError(
            "Quản lý chỉ xét duyệt phương án hoàn tiền."
        )

    if phuong_an.trang_thai != "CHO_DUYET":
        raise ValidationError(
            "Phương án không còn ở trạng thái Chờ phê duyệt."
        )

    if phuong_an.nguoi_de_xuat_id == quan_ly.pk:
        raise PermissionDenied(
            "Bạn không được tự phê duyệt phương án mình đề xuất."
        )

    if ApprovalRecord.objects.filter(
        ma_phuong_an=phuong_an
    ).exists():
        raise ValidationError("Phiên bản này đã có quyết định.")

    # Kiểm tra lại tính hợp lệ của phương án trước khi quyết định.
    phuong_an.full_clean()

    ket_qua = ApprovalRecord(
        ma_phuong_an=phuong_an,
        nguoi_phe_duyet=quan_ly,
        quyet_dinh=quyet_dinh,
        ly_do=ly_do,
    )
    ket_qua.full_clean()

    trang_thai_moi = (
        "SAN_SANG_THUC_HIEN"
        if quyet_dinh == "PHE_DUYET"
        else "TU_CHOI"
    )

    so_ban_ghi = CompensationAction.objects.filter(
        pk=phuong_an.pk,
        loai_phuong_an="HOAN_TIEN",
        trang_thai="CHO_DUYET",
    ).update(
        trang_thai=trang_thai_moi,
        thoi_diem_cap_nhat=timezone.now(),
    )

    if so_ban_ghi != 1:
        raise ValidationError(
            "Phương án đã thay đổi. Vui lòng tải lại trang."
        )

    ket_qua.save()

    TicketLog.objects.create(
        ticket=ticket,
        nguoi_thuc_hien=user,
        hanh_dong=(
            "PHE_DUYET_PHUONG_AN"
            if quyet_dinh == "PHE_DUYET"
            else "TU_CHOI_PHUONG_AN"
        ),
        noi_dung=(
            f"Quản lý {quan_ly.ho_ten} "
            f"{ket_qua.get_quyet_dinh_display().lower()} "
            f"phương án hoàn tiền V{phuong_an.phien_ban}, "
            f"hồ sơ #{ho_so.pk}.\n"
            f"Số tiền: {phuong_an.so_tien_hoan} "
            f"{phuong_an.don_vi_tien_te}.\n"
            f"Nhận xét/lý do: {ly_do or 'Không có nhận xét thêm'}.\n"
            f"Trạng thái: CHO_DUYET → {trang_thai_moi}."
        ),
    )

    return ket_qua


@transaction.atomic
def thu_hoi_gui_duyet_sai_nhanh(
    *,
    user,
    ma_ho_so,
    ma_phuong_an,
):
    """
    Giữ lại công cụ sửa dữ liệu cũ đã gửi nhầm nhánh.
    Không dùng cho luồng lập phương án hiện tại.
    """

    nhan_vien, ticket, ho_so = _lay_ho_so_de_xu_ly(
        user=user,
        ma_ho_so=ma_ho_so,
    )

    _kiem_tra_ticket_dang_cho_tham_dinh(ticket)

    phuong_an = (
        CompensationAction.objects.select_for_update()
        .filter(ma_ho_so=ho_so)
        .order_by("-phien_ban")
        .first()
    )

    if phuong_an is None or phuong_an.pk != ma_phuong_an:
        raise ValidationError(
            "Phương án không phải phiên bản mới nhất của hồ sơ."
        )

    if phuong_an.loai_phuong_an == "HOAN_TIEN":
        raise ValidationError(
            "Không dùng thao tác sửa nhánh cho phương án hoàn tiền."
        )

    if ApprovalRecord.objects.filter(
        ma_phuong_an=phuong_an
    ).exists():
        raise ValidationError(
            "Phương án đã có quyết định, cần xử lý riêng để giữ lịch sử."
        )

    if phuong_an.trang_thai != "CHO_DUYET":
        raise ValidationError(
            "Phương án không ở trạng thái gửi nhầm Chờ phê duyệt."
        )

    so_ban_ghi = CompensationAction.objects.filter(
        pk=phuong_an.pk,
        trang_thai="CHO_DUYET",
    ).update(
        trang_thai="DE_XUAT",
        thoi_diem_cap_nhat=timezone.now(),
    )

    if so_ban_ghi != 1:
        raise ValidationError("Trạng thái phương án đã thay đổi.")

    TicketLog.objects.create(
        ticket=ticket,
        nguoi_thuc_hien=user,
        hanh_dong="THU_HOI_GUI_DUYET",
        noi_dung=(
            f"Nhân viên {nhan_vien.ho_ten} thu hồi yêu cầu "
            f"duyệt nhầm phương án V{phuong_an.phien_ban}, "
            f"hồ sơ #{ho_so.pk}.\n"
            "Lý do: chỉ hoàn tiền cần quản lý phê duyệt; "
            "phương án này thuộc quyền nhân viên thẩm định.\n"
            "Trạng thái: CHO_DUYET → DE_XUAT."
        ),
    )

    phuong_an.refresh_from_db()
    return phuong_an