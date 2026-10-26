from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import Staff
from tickets.models import Ticket, TicketLog

from .models import ApprovalRecord, CompensationAction, DisputeCase


@transaction.atomic
def cap_nhat_thuc_hien(
    *,
    user,
    ma_ho_so,
    ma_phuong_an,
    ket_qua_thuc_hien,
    hoan_tat=False,
):
    """
    Lưu tiến độ hoặc xác nhận hoàn tất phương án.

    Khi hoàn tất:
    - Phương án chuyển DA_HOAN_TAT.
    - Theo dõi thẩm định chuyển COMPLETED.
    - Ticket vẫn IN_PROGRESS để CSKH hoàn tất theo Module 3.
    """

    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Bạn cần đăng nhập tài khoản đang hoạt động.")

    nhan_vien = Staff.objects.filter(
        ma_tai_khoan=user,
        vai_tro="ASSESSOR",
    ).first()

    if nhan_vien is None:
        raise PermissionDenied(
            "Chỉ nhân viên thẩm định được thực hiện phương án."
        )

    if not isinstance(hoan_tat, bool):
        raise ValidationError("Lựa chọn hoàn tất không hợp lệ.")

    if (
        not isinstance(ket_qua_thuc_hien, str)
        or len(ket_qua_thuc_hien.strip()) < 10
    ):
        raise ValidationError(
            "Nội dung tiến độ hoặc kết quả phải có ít nhất 10 ký tự."
        )

    ket_qua_thuc_hien = ket_qua_thuc_hien.strip()

    thong_tin = DisputeCase.objects.filter(
        pk=ma_ho_so,
        ma_nhan_vien_tham_dinh=nhan_vien,
    ).values("ma_ticket_id").first()

    if thong_tin is None:
        raise PermissionDenied(
            "Hồ sơ không tồn tại hoặc không được phân công cho bạn."
        )

    # Giữ cùng thứ tự khóa: Ticket -> hồ sơ -> phương án.
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

    if ho_so.trang_thai != "DA_KET_LUAN" or not ho_so.ket_luan.strip():
        raise ValidationError(
            "Hồ sơ phải có kết luận trước khi thực hiện phương án."
        )

    if (
        ticket.trang_thai != "IN_PROGRESS"
        or ticket.trang_thai_tham_dinh != "WAITING"
    ):
        raise ValidationError(
            "Ticket phải đang xử lý và đang chờ kết quả thẩm định."
        )

    don_hang = ho_so.ma_don_hang

    if (
        don_hang is None
        or don_hang.ma_khach_hang_id != ticket.khach_hang_id
    ):
        raise ValidationError(
            "Hồ sơ cần liên kết đúng đơn hàng của khách hàng."
        )

    phuong_an = (
        CompensationAction.objects.select_for_update()
        .filter(ma_ho_so=ho_so)
        .order_by("-phien_ban")
        .first()
    )

    if phuong_an is None or phuong_an.pk != ma_phuong_an:
        raise ValidationError(
            "Phương án đã thay đổi. Chỉ được thực hiện phiên bản mới nhất."
        )

    loai_hop_le = dict(
        CompensationAction.LOAI_PHUONG_AN_MOI_CHOICES
    )

    if phuong_an.loai_phuong_an not in loai_hop_le:
        raise ValidationError(
            "Phương án dùng mã dữ liệu cũ. Cần lập lại phương án "
            "theo quy trình hiện tại."
        )

    trang_thai_cho_phep = [
        "SAN_SANG_THUC_HIEN",
        "DANG_THUC_HIEN",
    ]

    # Tương thích phương án hoàn tiền được duyệt bằng code cũ.
    if phuong_an.loai_phuong_an == "HOAN_TIEN":
        trang_thai_cho_phep.append("DA_DUYET")

        da_duoc_duyet = ApprovalRecord.objects.filter(
            ma_phuong_an=phuong_an,
            quyet_dinh="PHE_DUYET",
            nguoi_phe_duyet__vai_tro="MANAGER",
        ).exclude(
            nguoi_phe_duyet_id=phuong_an.nguoi_de_xuat_id
        ).exists()

        if not da_duoc_duyet:
            raise ValidationError(
                "Phương án hoàn tiền chưa được quản lý phê duyệt."
            )

    if phuong_an.trang_thai not in trang_thai_cho_phep:
        raise ValidationError(
            "Phương án chưa được phép thực hiện hoặc đã hoàn tất."
        )

    now = timezone.now()
    trang_thai_cu = phuong_an.trang_thai

    phuong_an.ket_qua_thuc_hien = ket_qua_thuc_hien
    phuong_an.trang_thai = (
        "DA_HOAN_TAT" if hoan_tat else "DANG_THUC_HIEN"
    )
    phuong_an.thoi_diem_hoan_tat = now if hoan_tat else None
    phuong_an.full_clean()

    so_ban_ghi = CompensationAction.objects.filter(
        pk=phuong_an.pk,
        ma_ho_so=ho_so,
        trang_thai=trang_thai_cu,
        thoi_diem_cap_nhat=phuong_an.thoi_diem_cap_nhat,
    ).update(
        ket_qua_thuc_hien=ket_qua_thuc_hien,
        trang_thai=phuong_an.trang_thai,
        thoi_diem_hoan_tat=phuong_an.thoi_diem_hoan_tat,
        thoi_diem_cap_nhat=now,
    )

    if so_ban_ghi != 1:
        raise ValidationError(
            "Phương án vừa được cập nhật. Vui lòng tải lại trang."
        )

    if hoan_tat:
        # Trả kết quả chuyên môn; CSKH vẫn phụ trách Ticket.
        so_ticket = Ticket.objects.filter(
            pk=ticket.pk,
            trang_thai="IN_PROGRESS",
            trang_thai_tham_dinh="WAITING",
        ).update(
            trang_thai_tham_dinh="COMPLETED",
            thoi_diem_cap_nhat=now,
        )

        if so_ticket != 1:
            raise ValidationError(
                "Trạng thái Ticket vừa thay đổi. Vui lòng tải lại trang."
            )

    TicketLog.objects.create(
        ticket=ticket,
        nguoi_thuc_hien=user,
        hanh_dong=(
            "HOAN_TAT_PHUONG_AN"
            if hoan_tat
            else "CAP_NHAT_THUC_HIEN"
        ),
        noi_dung=(
            f"Nhân viên {nhan_vien.ho_ten} "
            f"{'hoàn tất' if hoan_tat else 'cập nhật tiến độ'} "
            f"phương án V{phuong_an.phien_ban}, "
            f"hồ sơ #{ho_so.pk}.\n"
            f"Loại: {phuong_an.get_loai_phuong_an_display()}.\n"
            f"Kết quả: {ket_qua_thuc_hien}"
            + (
                "\nĐã trả kết quả thẩm định về CSKH. "
                "Ticket tiếp tục ở trạng thái đang xử lý."
                if hoan_tat else ""
            )
        ),
    )

    phuong_an.refresh_from_db()
    return phuong_an