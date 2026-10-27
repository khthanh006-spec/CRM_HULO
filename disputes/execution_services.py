from decimal import Decimal, ROUND_DOWN

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.models import Staff
from tickets.models import Ticket, TicketLog

from .models import (
    ApprovalRecord,
    CompensationAction,
    DisputeCase,
    Order,
    OrderItem,
)
from .plan_services import _cac_phuong_an_phai_tinh


def _kiem_tra_gioi_han_truoc_khi_hoan_tat(*, don_hang, phuong_an):
    """
    Kiểm tra lại phương án trước khi ghi nhận hoàn tất.

    Tính cả những phương án khác đã hoàn tất hoặc đang giữ phần
    tiền/số lượng. Không cộng phương án hiện tại hai lần.

    Hàm này được gọi trong transaction sau khi khóa đơn hàng.
    """
    loai = phuong_an.loai_phuong_an

    if loai not in {"HOAN_TIEN", "DOI_HANG", "GIAO_BO_SUNG"}:
        return

    if phuong_an.ma_chi_tiet_don_id is None:
        raise ValidationError(
            "Phương án chưa xác định sản phẩm trong đơn. "
            "Cần đối soát trước khi hoàn tất."
        )

    chi_tiet = (
        OrderItem.objects.select_for_update()
        .filter(
            pk=phuong_an.ma_chi_tiet_don_id,
            ma_don_hang=don_hang,
        )
        .first()
    )

    if chi_tiet is None:
        raise ValidationError(
            "Sản phẩm không thuộc đơn hàng của hồ sơ."
        )

    if (
        phuong_an.so_luong is None
        or phuong_an.so_luong < 1
        or phuong_an.so_luong > chi_tiet.so_luong
    ):
        raise ValidationError(
            "Số lượng xử lý không hợp lệ. "
            "Cần đối soát trước khi hoàn tất."
        )

    phuong_an_khac = _cac_phuong_an_phai_tinh(
        don_hang=don_hang,
    ).exclude(pk=phuong_an.pk)

    if loai == "HOAN_TIEN":
        hoan_tien_khac = phuong_an_khac.filter(
            loai_phuong_an="HOAN_TIEN",
        )

        if hoan_tien_khac.filter(
            ma_chi_tiet_don__isnull=True
        ).exists():
            raise ValidationError(
                "Đơn hàng có phương án hoàn tiền đang giữ chỗ "
                "hoặc lịch sử chưa xác định dòng sản phẩm. "
                "Cần đối soát trước khi hoàn tất."
            )

        da_hoac_dang_hoan = hoan_tien_khac.filter(
            ma_chi_tiet_don=chi_tiet,
        ).aggregate(
            tong=Sum("so_tien_hoan")
        )["tong"] or Decimal("0")

        gia_tri_phan_hang = (
            chi_tiet.gia_tri_da_thanh_toan
            * Decimal(phuong_an.so_luong)
            / Decimal(chi_tiet.so_luong)
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_DOWN,
        )

        gioi_han = max(
            Decimal("0"),
            gia_tri_phan_hang - da_hoac_dang_hoan,
        )

        if (
            phuong_an.so_tien_hoan is None
            or phuong_an.so_tien_hoan <= 0
            or phuong_an.so_tien_hoan > gioi_han
        ):
            raise ValidationError(
                "Không thể hoàn tất: số tiền của phương án "
                "vượt phần còn được hoàn sau khi tính các "
                "phương án khác. Cần đối soát trước."
            )

    else:
        hang_khac = phuong_an_khac.filter(
            loai_phuong_an__in=[
                "DOI_HANG",
                "GIAO_BO_SUNG",
                "GUI_LAI_HANG",
            ],
        )

        if hang_khac.filter(
            ma_chi_tiet_don__isnull=True
        ).exists():
            raise ValidationError(
                "Đơn hàng có phương án giao/đổi đang giữ chỗ "
                "hoặc lịch sử chưa xác định dòng sản phẩm. "
                "Cần đối soát trước khi hoàn tất."
            )

        cung_dong = hang_khac.filter(
            ma_chi_tiet_don=chi_tiet,
        )

        if cung_dong.filter(so_luong__isnull=True).exists():
            raise ValidationError(
                "Có phương án giao/đổi trước chưa ghi số lượng. "
                "Cần đối soát trước khi hoàn tất."
            )

        da_hoac_dang_xu_ly = cung_dong.aggregate(
            tong=Sum("so_luong")
        )["tong"] or 0

        con_lai = max(
            0,
            chi_tiet.so_luong - da_hoac_dang_xu_ly,
        )

        if phuong_an.so_luong > con_lai:
            raise ValidationError(
                "Không thể hoàn tất: tổng số lượng giao/đổi "
                "vượt số lượng đã mua sau khi tính các "
                "phương án khác. Cần đối soát trước."
            )


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
        raise PermissionDenied(
            "Bạn cần đăng nhập tài khoản đang hoạt động."
        )

    nhan_vien = Staff.objects.filter(
        ma_tai_khoan=user,
        vai_tro="ASSESSOR",
    ).first()

    if nhan_vien is None:
        raise PermissionDenied(
            "Chỉ nhân viên thẩm định được thực hiện phương án."
        )

    if not isinstance(hoan_tat, bool):
        raise ValidationError(
            "Lựa chọn hoàn tất không hợp lệ."
        )

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

    # Thứ tự khóa: Ticket -> hồ sơ -> đơn hàng -> phương án.
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

    if (
        ho_so.trang_thai != "DA_KET_LUAN"
        or not (ho_so.ket_luan or "").strip()
    ):
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

    if not ho_so.ma_don_hang_id:
        raise ValidationError(
            "Hồ sơ cần liên kết đúng đơn hàng của khách hàng."
        )

    # Khóa cùng đơn hàng mà service lập phương án sử dụng.
    don_hang = Order.objects.select_for_update().get(
        pk=ho_so.ma_don_hang_id
    )

    if don_hang.ma_khach_hang_id != ticket.khach_hang_id:
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
            "Phương án đã thay đổi. "
            "Chỉ được thực hiện phiên bản mới nhất."
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

    if phuong_an.loai_phuong_an == "HOAN_TIEN":
        # Tương thích phương án duyệt bằng code cũ.
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

    # Chỉ đánh dấu hoàn tất khi giới hạn vẫn hợp lệ.
    if hoan_tat:
        _kiem_tra_gioi_han_truoc_khi_hoan_tat(
            don_hang=don_hang,
            phuong_an=phuong_an,
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