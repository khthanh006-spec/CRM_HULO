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


@transaction.atomic
def gui_phuong_an_phe_duyet(*, user, ma_ho_so, ma_phuong_an):
    """
    Chỉ gửi phương án hoàn tiền đến quản lý phê duyệt.
    """
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
            "Hồ sơ phải có kết luận trước khi gửi phê duyệt."
        )

    phuong_an = (
        CompensationAction.objects.select_for_update()
        .filter(ma_ho_so=ho_so)
        .order_by("-phien_ban")
        .first()
    )

    if phuong_an is None:
        raise ValidationError(
            "Hồ sơ chưa có phương án xử lý."
        )

    if phuong_an.pk != ma_phuong_an:
        raise ValidationError(
            "Phương án đã thay đổi. Vui lòng tải lại trang."
        )

    if phuong_an.loai_phuong_an != "HOAN_TIEN":
        raise ValidationError(
            "Chỉ phương án hoàn tiền cần quản lý phê duyệt. "
            "Phương án này do nhân viên thẩm định quyết định."
        )

    if phuong_an.trang_thai != "DE_XUAT":
        raise ValidationError(
            "Chỉ được gửi phương án đang ở trạng thái Đã đề xuất."
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
            "Phương án đã được gửi hoặc trạng thái đã thay đổi."
        )

    TicketLog.objects.create(
        ticket=ticket,
        nguoi_thuc_hien=user,
        hanh_dong="GUI_PHE_DUYET",
        noi_dung=(
            f"Nhân viên {nhan_vien.ho_ten} gửi phương án "
            f"hoàn tiền V{phuong_an.phien_ban} "
            f"của hồ sơ #{ho_so.pk} đến quản lý.\n"
            f"Số tiền đề xuất hoàn: {phuong_an.so_tien_hoan} "
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
    ly_do,
):
    """
    Quản lý phê duyệt hoặc yêu cầu điều chỉnh phương án hoàn tiền.
    """
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied(
            "Bạn cần đăng nhập bằng tài khoản hoạt động."
        )

    quan_ly = Staff.objects.filter(
        ma_tai_khoan=user,
        vai_tro="MANAGER",
    ).first()

    if quan_ly is None:
        raise PermissionDenied(
            "Chỉ tài khoản có vai trò Quản lý "
            "được phê duyệt hoàn tiền."
        )

    if quyet_dinh not in dict(ApprovalRecord.QUYET_DINH_CHOICES):
        raise ValidationError(
            "Quyết định không hợp lệ."
        )

    if not isinstance(ly_do, str) or not ly_do.strip():
        raise ValidationError(
            "Bạn cần nhập nhận xét hoặc lý do."
        )

    thong_tin = DisputeCase.objects.filter(
        pk=ma_ho_so
    ).values("ma_ticket_id").first()

    if thong_tin is None:
        raise ValidationError(
            "Hồ sơ không tồn tại."
        )

    # Khóa Ticket trước, sau đó khóa hồ sơ và phương án.
    ticket = Ticket.objects.select_for_update().get(
        pk=thong_tin["ma_ticket_id"]
    )

    ho_so = DisputeCase.objects.select_for_update().get(
        pk=ma_ho_so,
        ma_ticket_id=ticket.pk,
    )

    _kiem_tra_ticket_dang_cho_tham_dinh(ticket)

    if (
        ho_so.trang_thai != "DA_KET_LUAN"
        or not ho_so.ket_luan.strip()
    ):
        raise ValidationError(
            "Hồ sơ chưa đủ điều kiện phê duyệt."
        )

    phuong_an = (
        CompensationAction.objects.select_for_update()
        .filter(ma_ho_so=ho_so)
        .order_by("-phien_ban")
        .first()
    )

    if phuong_an is None or phuong_an.pk != ma_phuong_an:
        raise ValidationError(
            "Phiên bản phương án đã thay đổi. "
            "Vui lòng tải lại trang."
        )

    if phuong_an.loai_phuong_an != "HOAN_TIEN":
        raise ValidationError(
            "Quản lý chỉ xét duyệt phương án hoàn tiền. "
            "Phương án này thuộc quyền nhân viên thẩm định."
        )

    if phuong_an.trang_thai != "CHO_DUYET":
        raise ValidationError(
            "Phương án không còn ở trạng thái Chờ phê duyệt."
        )

    if ApprovalRecord.objects.filter(
        ma_phuong_an=phuong_an
    ).exists():
        raise ValidationError(
            "Phương án đã có quyết định."
        )

    ket_qua = ApprovalRecord(
        ma_phuong_an=phuong_an,
        nguoi_phe_duyet=quan_ly,
        quyet_dinh=quyet_dinh,
        ly_do=ly_do.strip(),
    )

    ket_qua.full_clean()

    trang_thai_moi = (
        "DA_DUYET"
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
            f"phương án hoàn tiền V{phuong_an.phien_ban} "
            f"của hồ sơ #{ho_so.pk}.\n"
            f"Nhận xét/lý do: {ket_qua.ly_do}"
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
    Thu hồi phương án không phải hoàn tiền đã gửi quản lý nhầm.
    Giữ nguyên phiên bản, nội dung và lịch sử trước đó.
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
            "Hoàn tiền thuộc nhánh quản lý xét duyệt, "
            "không thu hồi bằng thao tác sửa nhánh này."
        )

    if ApprovalRecord.objects.filter(
        ma_phuong_an=phuong_an
    ).exists():
        raise ValidationError(
            "Phương án đã có quyết định. "
            "Cần xử lý riêng để giữ đúng lịch sử."
        )

    if phuong_an.trang_thai != "CHO_DUYET":
        raise ValidationError(
            "Chỉ sửa phương án đang bị đưa nhầm "
            "vào Chờ phê duyệt."
        )

    so_ban_ghi = CompensationAction.objects.filter(
        pk=phuong_an.pk,
        trang_thai="CHO_DUYET",
    ).update(
        trang_thai="DE_XUAT",
        thoi_diem_cap_nhat=timezone.now(),
    )

    if so_ban_ghi != 1:
        raise ValidationError(
            "Trạng thái phương án đã thay đổi."
        )

    TicketLog.objects.create(
        ticket=ticket,
        nguoi_thuc_hien=user,
        hanh_dong="THU_HOI_GUI_DUYET",
        noi_dung=(
            f"Nhân viên {nhan_vien.ho_ten} thu hồi yêu cầu "
            f"duyệt nhầm của phương án V{phuong_an.phien_ban}, "
            f"hồ sơ #{ho_so.pk}.\n"
            f"Loại: {phuong_an.get_loai_phuong_an_display()}.\n"
            "Lý do: sửa luồng theo BPMN TO-BE; "
            "chỉ hoàn tiền cần quản lý xét duyệt. "
            "Phương án này thuộc quyền quyết định "
            "của nhân viên thẩm định.\n"
            "Trạng thái: CHO_DUYET → DE_XUAT."
        ),
    )

    phuong_an.refresh_from_db()
    return phuong_an