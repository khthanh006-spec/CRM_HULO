from accounts.models import Staff

from .reconsideration_models import ReconsiderationRecord


def du_dieu_kien_lap_phuong_an(user, ho_so, phuong_an):
    if not user.is_authenticated or not user.is_active:
        return False

    duoc_phan_cong = Staff.objects.filter(
        pk=ho_so.ma_nhan_vien_tham_dinh_id,
        ma_tai_khoan=user,
        vai_tro="ASSESSOR",
    ).exists()

    if not duoc_phan_cong:
        return False

    ticket = ho_so.ma_ticket

    if (
        ho_so.trang_thai != "DA_KET_LUAN"
        or not (ho_so.ket_luan or "").strip()
        or ticket.trang_thai != "IN_PROGRESS"
        or ticket.trang_thai_tham_dinh != "WAITING"
        or (
            ho_so.ma_don_hang_id
            and ho_so.ma_don_hang.ma_khach_hang_id
            != ticket.khach_hang_id
        )
    ):
        return False

    cac_lan_dang_xem = ReconsiderationRecord.objects.filter(
        ma_ho_so=ho_so,
        trang_thai="DANG_XEM_XET",
    )

    if phuong_an is None:
        return not cac_lan_dang_xem.exists()

    if phuong_an.trang_thai in {"DE_XUAT", "TU_CHOI"}:
        return not cac_lan_dang_xem.exists()

    if phuong_an.trang_thai != "DA_HOAN_TAT":
        return False

    if (
        ticket.trang_thai_xac_nhan != "DISAGREED"
        or ticket.thoi_diem_xac_nhan is None
    ):
        return False

    return cac_lan_dang_xem.filter(
        phuong_an_truoc=phuong_an,
        thoi_diem_phan_hoi=ticket.thoi_diem_xac_nhan,
        phuong_an_moi__isnull=True,
    ).exists()