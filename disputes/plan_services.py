from decimal import Decimal, InvalidOperation, ROUND_DOWN

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum

from tickets.models import TicketLog

from .models import CompensationAction, Order, OrderItem
from .reconsideration_models import ReconsiderationRecord
from .services import (
    _kiem_tra_ticket_dang_cho_tham_dinh,
    _lay_ho_so_de_xu_ly,
)


# Các trạng thái đang giữ phần tiền hoặc số lượng đề xuất.
TRANG_THAI_DANG_GIU = [
    "DE_XUAT",
    "CHO_DUYET",
    "SAN_SANG_THUC_HIEN",
    "DANG_THUC_HIEN",
    "DA_DUYET",  # Dữ liệu cũ.
]


def _cac_phuong_an_phai_tinh(*, don_hang, phuong_an_thay_the=None):
    """
    Các phương án đã hoàn tất hoặc đang giữ tiền/số lượng.

    Khi điều chỉnh phiên bản chưa thực hiện, không cộng phiên bản
    đang được thay thế. Phiên bản đã hoàn tất vẫn phải được tính.
    """
    queryset = CompensationAction.objects.filter(
        ma_ho_so__ma_don_hang=don_hang,
    ).filter(
        Q(trang_thai__in=TRANG_THAI_DANG_GIU)
        | Q(trang_thai__in=["DA_HOAN_TAT", "DA_THUC_HIEN"])
        | Q(thoi_diem_hoan_tat__isnull=False)
    )

    if (
        phuong_an_thay_the is not None
        and phuong_an_thay_the.trang_thai in {"DE_XUAT", "TU_CHOI"}
        and phuong_an_thay_the.thoi_diem_hoan_tat is None
    ):
        queryset = queryset.exclude(pk=phuong_an_thay_the.pk)

    return queryset


@transaction.atomic
def luu_phuong_an_theo_bpmn(
    *,
    user,
    ma_ho_so,
    loai_phuong_an,
    noi_dung,
    ly_do,
    so_tien_hoan,
    phien_ban_hien_tai,
    ma_chi_tiet_don=None,
    so_luong=None,
    dia_chi_nhan="",
    ly_do_tu_choi="",
):
    nhan_vien, ticket, ho_so = _lay_ho_so_de_xu_ly(
        user=user,
        ma_ho_so=ma_ho_so,
    )

    _kiem_tra_ticket_dang_cho_tham_dinh(ticket)

    if (
        ho_so.trang_thai != "DA_KET_LUAN"
        or not (ho_so.ket_luan or "").strip()
    ):
        raise ValidationError(
            "Hồ sơ phải có kết luận trước khi lập phương án."
        )

    if not ho_so.ma_don_hang_id:
        raise ValidationError(
            "Hồ sơ cần được liên kết với đơn hàng."
        )

    # Các thao tác lập phương án phải khóa cùng đơn hàng.
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
        raise ValidationError("Loại phương án không hợp lệ.")

    if not isinstance(noi_dung, str) or not noi_dung.strip():
        raise ValidationError("Bạn cần nhập nội dung phương án.")

    if not isinstance(ly_do, str) or not ly_do.strip():
        raise ValidationError(
            "Bạn cần nhập căn cứ đề xuất hoặc lý do điều chỉnh."
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
            "Phương án đã thay đổi hoặc biểu mẫu đã được gửi. "
            "Vui lòng tải lại trang."
        )

    lan_xem_xet = (
        ReconsiderationRecord.objects.select_for_update()
        .filter(
            ma_ho_so=ho_so,
            trang_thai="DANG_XEM_XET",
        )
        .first()
    )

    sau_hoan_tat = (
        phuong_an_cu is not None
        and phuong_an_cu.trang_thai == "DA_HOAN_TAT"
    )

    if sau_hoan_tat:
        if (
            lan_xem_xet is None
            or lan_xem_xet.phuong_an_truoc_id != phuong_an_cu.pk
            or ticket.trang_thai_xac_nhan != "DISAGREED"
            or ticket.thoi_diem_xac_nhan
            != lan_xem_xet.thoi_diem_phan_hoi
        ):
            raise ValidationError(
                "Cần tiếp nhận đúng phản hồi xem xét lại "
                "trước khi lập phiên bản phương án mới."
            )
    else:
        if lan_xem_xet is not None:
            raise ValidationError(
                "Lần xem xét lại không khớp phương án hiện tại."
            )

        if phuong_an_cu and phuong_an_cu.trang_thai not in {
            "DE_XUAT",
            "TU_CHOI",
        }:
            raise ValidationError(
                "Phương án hiện tại không được phép điều chỉnh "
                "trực tiếp ở bước này."
            )

    chi_tiet = None

    if loai_phuong_an in {
        "HOAN_TIEN",
        "DOI_HANG",
        "GIAO_BO_SUNG",
    }:
        if (
            isinstance(ma_chi_tiet_don, bool)
            or not isinstance(ma_chi_tiet_don, int)
        ):
            raise ValidationError(
                "Bạn cần chọn sản phẩm trong đơn hàng."
            )

        chi_tiet = (
            OrderItem.objects.select_for_update()
            .filter(
                pk=ma_chi_tiet_don,
                ma_don_hang=don_hang,
            )
            .first()
        )

        if chi_tiet is None:
            raise ValidationError(
                "Sản phẩm không thuộc đơn hàng của hồ sơ."
            )

        if (
            isinstance(so_luong, bool)
            or not isinstance(so_luong, int)
            or so_luong < 1
            or so_luong > chi_tiet.so_luong
        ):
            raise ValidationError(
                "Số lượng xử lý phải lớn hơn 0 "
                "và không vượt số lượng đã mua."
            )

    try:
        so_tien = Decimal(str(so_tien_hoan))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Số tiền hoàn không hợp lệ.")

    if not so_tien.is_finite() or so_tien < 0:
        raise ValidationError("Số tiền hoàn không hợp lệ.")

    dia_chi = (
        dia_chi_nhan.strip()
        if isinstance(dia_chi_nhan, str) else ""
    )

    ly_do_tu_choi_sach = (
        ly_do_tu_choi.strip()
        if isinstance(ly_do_tu_choi, str) else ""
    )

    phuong_an_phai_tinh = _cac_phuong_an_phai_tinh(
        don_hang=don_hang,
        phuong_an_thay_the=phuong_an_cu,
    )

    if loai_phuong_an == "HOAN_TIEN":
        if so_tien <= 0:
            raise ValidationError(
                "Số tiền đề xuất hoàn phải lớn hơn 0."
            )

        hoan_tien_khac = phuong_an_phai_tinh.filter(
            loai_phuong_an="HOAN_TIEN"
        )

        if hoan_tien_khac.filter(
            ma_chi_tiet_don__isnull=True
        ).exists():
            raise ValidationError(
                "Đơn hàng có phương án hoàn tiền đang giữ chỗ "
                "hoặc lịch sử chưa xác định dòng sản phẩm. "
                "Cần đối soát trước."
            )

        da_hoac_dang_hoan = hoan_tien_khac.filter(
            ma_chi_tiet_don=chi_tiet
        ).aggregate(
            tong=Sum("so_tien_hoan")
        )["tong"] or Decimal("0")

        gia_tri_phan_hang = (
            chi_tiet.gia_tri_da_thanh_toan
            * Decimal(so_luong)
            / Decimal(chi_tiet.so_luong)
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_DOWN,
        )

        # Chưa phân biệt từng đơn vị hàng; trừ toàn bộ khoản
        # đã hoặc đang hoàn của cùng dòng sản phẩm.
        gioi_han = max(
            Decimal("0"),
            gia_tri_phan_hang - da_hoac_dang_hoan,
        )

        if so_tien > gioi_han:
            raise ValidationError(
                "Số tiền đề xuất vượt phần còn được hoàn. "
                f"Giá trị phần hàng: {gia_tri_phan_hang}; "
                f"đã hoặc đang đề xuất hoàn: {da_hoac_dang_hoan}; "
                f"tối đa đề xuất thêm: {gioi_han} "
                f"{don_hang.don_vi_tien_te}."
            )

        trang_thai_moi = "CHO_DUYET"
        dia_chi = ""
        ly_do_tu_choi_sach = ""

    else:
        if so_tien != 0:
            raise ValidationError(
                "Phương án không phải hoàn tiền "
                "phải có số tiền hoàn bằng 0."
            )

        trang_thai_moi = "SAN_SANG_THUC_HIEN"

        if loai_phuong_an in {"DOI_HANG", "GIAO_BO_SUNG"}:
            if not dia_chi:
                raise ValidationError(
                    "Bạn cần nhập địa chỉ nhận hàng."
                )

            hang_khac = phuong_an_phai_tinh.filter(
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
                    "Cần đối soát trước."
                )

            cung_dong = hang_khac.filter(
                ma_chi_tiet_don=chi_tiet
            )

            if cung_dong.filter(so_luong__isnull=True).exists():
                raise ValidationError(
                    "Có phương án giao/đổi trước chưa ghi số lượng. "
                    "Cần đối soát trước khi đề xuất thêm."
                )

            da_hoac_dang_xu_ly = cung_dong.aggregate(
                tong=Sum("so_luong")
            )["tong"] or 0

            con_lai = max(
                0,
                chi_tiet.so_luong - da_hoac_dang_xu_ly,
            )

            if so_luong > con_lai:
                raise ValidationError(
                    f"Dòng hàng đã hoặc đang giao/đổi xử lý "
                    f"{da_hoac_dang_xu_ly} sản phẩm; "
                    f"còn tối đa {con_lai}. "
                    "Nếu lần giao trước thất bại, cần xác minh "
                    "kết quả lần đó trước khi tạo lần giao mới."
                )

            ly_do_tu_choi_sach = ""

        elif loai_phuong_an == "TU_CHOI_HO_TRO":
            if not ly_do_tu_choi_sach:
                raise ValidationError(
                    "Bạn cần nhập lý do từ chối hỗ trợ."
                )

            chi_tiet = None
            so_luong = None
            dia_chi = ""

    phuong_an = CompensationAction(
        ma_ho_so=ho_so,
        phien_ban=phien_ban_moi_nhat + 1,
        loai_phuong_an=loai_phuong_an,
        noi_dung=noi_dung.strip(),
        ly_do=ly_do.strip(),
        so_tien_hoan=so_tien,
        don_vi_tien_te=don_hang.don_vi_tien_te,
        ma_chi_tiet_don=chi_tiet,
        so_luong=so_luong,
        dia_chi_nhan=dia_chi,
        ly_do_tu_choi=ly_do_tu_choi_sach,
        nguoi_de_xuat=nhan_vien,
        trang_thai=trang_thai_moi,
    )

    phuong_an.full_clean()

    # Giữ nguyên lịch sử của phương án đã hoàn tất.
    if phuong_an_cu and not sau_hoan_tat:
        phuong_an_cu.trang_thai = "DA_THAY_THE"
        phuong_an_cu.save(
            update_fields=["trang_thai", "thoi_diem_cap_nhat"]
        )

    phuong_an.save()

    if lan_xem_xet is not None:
        lan_xem_xet.phuong_an_moi = phuong_an
        lan_xem_xet.trang_thai = "DA_LAP_PHUONG_AN"
        lan_xem_xet.full_clean()
        lan_xem_xet.save(
            update_fields=["phuong_an_moi", "trang_thai"]
        )

    TicketLog.objects.create(
        ticket=ticket,
        nguoi_thuc_hien=user,
        hanh_dong="DE_XUAT_PHUONG_AN",
        noi_dung=(
            f"Hồ sơ #{ho_so.pk} - "
            f"Phương án V{phuong_an.phien_ban}.\n"
            f"Loại: {phuong_an.get_loai_phuong_an_display()}.\n"
            f"Trạng thái: {phuong_an.get_trang_thai_display()}.\n"
            f"Số tiền đề xuất thêm: {so_tien} "
            f"{don_hang.don_vi_tien_te}.\n"
            f"Sản phẩm: {chi_tiet or 'Không áp dụng'}.\n"
            f"Số lượng: {so_luong or 'Không áp dụng'}.\n"
            f"Địa chỉ nhận: {dia_chi}\n"
            f"Nội dung: {phuong_an.noi_dung}\n"
            f"Căn cứ/lý do: {phuong_an.ly_do}\n"
            f"Lý do từ chối hỗ trợ: {ly_do_tu_choi_sach}\n"
            f"Lần xem xét lại: "
            f"{lan_xem_xet.pk if lan_xem_xet else 'Không áp dụng'}."
        ),
    )

    if loai_phuong_an == "HOAN_TIEN":
        TicketLog.objects.create(
            ticket=ticket,
            nguoi_thuc_hien=user,
            hanh_dong="GUI_PHE_DUYET",
            noi_dung=(
                f"Đã gửi phương án hoàn tiền "
                f"V{phuong_an.phien_ban} của hồ sơ #{ho_so.pk} "
                "vào danh sách chờ quản lý xét duyệt. "
                "Quyết định của phiên bản trước không được "
                "dùng để phê duyệt phiên bản mới."
            ),
        )

    return phuong_an