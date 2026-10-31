from accounts.permissions import get_user_role

from .reconsideration_models import ReconsiderationRecord


def tao_context_xem_xet_lai(*, user, ho_so, phuong_an):
    ticket = ho_so.ma_ticket

    lan_xem_xet = (
        ReconsiderationRecord.objects
        .select_related(
            "phuong_an_truoc",
            "phuong_an_moi",
            "nguoi_ket_thuc",
        )
        .filter(ma_ho_so=ho_so)
        .order_by("-thoi_diem_tao", "-pk")
        .first()
    )

    duoc_thao_tac = (
        user.is_authenticated
        and user.is_active
        and get_user_role(user) == "ASSESSOR"
        and ho_so.ma_nhan_vien_tham_dinh_id is not None
        and ho_so.ma_nhan_vien_tham_dinh.ma_tai_khoan_id == user.pk
        and ho_so.ma_nhan_vien_tham_dinh.vai_tro == "ASSESSOR"
    )

    da_tiep_nhan_phan_hoi = False

    if ticket.thoi_diem_xac_nhan is not None:
        da_tiep_nhan_phan_hoi = (
            ReconsiderationRecord.objects.filter(
                ma_ho_so=ho_so,
                thoi_diem_phan_hoi=ticket.thoi_diem_xac_nhan,
            ).exists()
        )

    co_lan_dang_mo = ReconsiderationRecord.objects.filter(
        ma_ho_so=ho_so,
        trang_thai="DANG_XEM_XET",
    ).exists()

    phuong_an_da_hoan_tat = (
        phuong_an is not None
        and phuong_an.trang_thai == "DA_HOAN_TAT"
        and phuong_an.thoi_diem_hoan_tat is not None
    )

    phan_hoi_sau_hoan_tat = (
        phuong_an_da_hoan_tat
        and ticket.thoi_diem_xac_nhan is not None
        and ticket.thoi_diem_xac_nhan > phuong_an.thoi_diem_hoan_tat
    )

    co_the_tiep_nhan_xem_xet = (
        duoc_thao_tac
        and ticket.trang_thai == "IN_PROGRESS"
        and ticket.trang_thai_tham_dinh == "COMPLETED"
        and ticket.trang_thai_xac_nhan == "DISAGREED"
        and bool((ticket.ly_do_khong_dong_y or "").strip())
        and ho_so.trang_thai == "DA_KET_LUAN"
        and bool((ho_so.ket_luan or "").strip())
        and ho_so.ma_don_hang_id is not None
        and ho_so.ma_don_hang.ma_khach_hang_id == ticket.khach_hang_id
        and phan_hoi_sau_hoan_tat
        and not da_tiep_nhan_phan_hoi
        and not co_lan_dang_mo
    )

    co_the_ghi_ket_qua_xem_xet = (
        duoc_thao_tac
        and lan_xem_xet is not None
        and lan_xem_xet.trang_thai == "DANG_XEM_XET"
        and lan_xem_xet.phuong_an_moi_id is None
        and ticket.trang_thai == "IN_PROGRESS"
        and ticket.trang_thai_tham_dinh == "WAITING"
        and ticket.trang_thai_xac_nhan == "DISAGREED"
        and ticket.thoi_diem_xac_nhan == lan_xem_xet.thoi_diem_phan_hoi
        and (ticket.ly_do_khong_dong_y or "").strip()
        == lan_xem_xet.ly_do_khach_hang.strip()
        and ho_so.trang_thai == "DA_KET_LUAN"
        and bool((ho_so.ket_luan or "").strip())
        and phuong_an_da_hoan_tat
        and lan_xem_xet.phuong_an_truoc_id == phuong_an.pk
    )

    co_the_xem_ket_qua_xem_xet = (
        duoc_thao_tac
        and lan_xem_xet is not None
        and lan_xem_xet.trang_thai == "DA_KET_THUC"
    )

    return {
        "lan_xem_xet_moi_nhat": lan_xem_xet,
        "co_the_tiep_nhan_xem_xet": co_the_tiep_nhan_xem_xet,
        "co_the_ghi_ket_qua_xem_xet": co_the_ghi_ket_qua_xem_xet,
        "co_the_xem_ket_qua_xem_xet": co_the_xem_ket_qua_xem_xet,
        "da_tiep_nhan_phan_hoi_xem_xet": da_tiep_nhan_phan_hoi,
    }