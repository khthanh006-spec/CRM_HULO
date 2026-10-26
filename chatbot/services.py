
import re
import unicodedata

from .models import ChatRule


# Chuẩn hóa câu hỏi để dễ tìm từ khóa
def chuan_hoa_van_ban(van_ban):
    van_ban = (van_ban or "").lower()
    van_ban = van_ban.replace("đ", "d")

    van_ban = unicodedata.normalize("NFD", van_ban)

    van_ban = "".join(
        ky_tu for ky_tu in van_ban
        if unicodedata.category(ky_tu) != "Mn"
    )

    van_ban = re.sub(r"[^a-z0-9]+", " ", van_ban)

    return " ".join(van_ban.split())


# Tìm câu trả lời theo quy tắc Chatbot
def tra_loi_chatbot(cau_hoi):
    cau_hoi_chuan = chuan_hoa_van_ban(cau_hoi)

    if not cau_hoi_chuan:
        return {
            "cau_tra_loi": "Vui lòng nhập câu hỏi.",
            "quy_tac": None
        }

    # Chỉ lấy các quy tắc đang hoạt động
    danh_sach_quy_tac = ChatRule.objects.filter(
        dang_hoat_dong=True
    ).exclude(
        cau_tra_loi__isnull=True
    ).exclude(
        cau_tra_loi=""
    ).order_by(
        "-thu_tu_uu_tien",
        "ma_quy_tac"
    )

    # Duyệt qua các quy tắc
    for quy_tac in danh_sach_quy_tac:
        tu_khoa = chuan_hoa_van_ban(quy_tac.tu_khoa)

        if tu_khoa and (
            f" {tu_khoa} " in f" {cau_hoi_chuan} "
        ):
            return {
                "cau_tra_loi": quy_tac.cau_tra_loi,
                "quy_tac": quy_tac
            }

    # Không tìm được từ khóa phù hợp
    return {
        "cau_tra_loi": (
            "HULO Assistant chưa tìm thấy câu trả lời "
            "phù hợp. Bạn có thể hỏi theo cách khác "
            "hoặc chọn Cần nhân viên hỗ trợ."
        ),
        "quy_tac": None
    }

# ==================================================
# UC-2.6: CHUẨN BỊ DỮ LIỆU M2 CHO MODULE 3
# Chưa tạo Ticket, chưa gọi service M3
# ==================================================

def chuan_bi_yeu_cau_cho_m3(yeu_cau):

    # Bước 1: Kiểm tra bản nháp
    if not isinstance(yeu_cau, dict):
        raise ValueError("Bản nháp yêu cầu không hợp lệ.")

    thong_tin = yeu_cau.get('thong_tin')

    if not isinstance(thong_tin, dict):
        raise ValueError("Chưa có thông tin yêu cầu.")

    # Bước 2: Lấy mã chống tạo Ticket trùng
    source_request_id = yeu_cau.get(
        'source_request_id'
    )

    if (
        not isinstance(source_request_id, str)
        or not source_request_id.strip()
    ):
        raise ValueError("Yêu cầu chưa có mã nguồn.")

    # Bước 3: Lấy thông tin từ UC-2.3 và UC-2.4
    loai_van_de = yeu_cau.get('loai_van_de', '')

    tieu_de = str(
        thong_tin.get('tieu_de') or ''
    ).strip()

    mo_ta = str(
        thong_tin.get('mo_ta') or ''
    ).strip()

    ma_don_hang = str(
        thong_tin.get('ma_don_hang') or ''
    ).strip()

    email = str(
        thong_tin.get('email_lien_he') or ''
    ).strip()

    so_dien_thoai = str(
        thong_tin.get('so_dien_thoai') or ''
    ).strip()

    if not tieu_de or not mo_ta or not loai_van_de:
        raise ValueError("Thông tin yêu cầu chưa đầy đủ.")

    # Bước 4: Tổng hợp nội dung để M3 xử lý
    noi_dung = (
        f"Loại vấn đề: {loai_van_de}\n"
        f"Mã đơn hàng: {ma_don_hang or 'Không cung cấp'}\n"
        f"Mô tả: {mo_ta}\n"
        f"Email liên hệ: {email or 'Không cung cấp'}\n"
        f"Số điện thoại: {so_dien_thoai or 'Không cung cấp'}"
    )

    # Bước 5: Lấy danh sách bằng chứng
    bang_chung = yeu_cau.get('bang_chung', [])

    if not isinstance(bang_chung, list):
        bang_chung = []

    # Bước 6: Trả về dữ liệu đã chuẩn bị
    return {
        'source_request_id': source_request_id,
        'tieu_de': tieu_de,
        'noi_dung': noi_dung,
        'muc_uu_tien': 'MEDIUM',
        'loai_van_de_m2': loai_van_de,
        'bang_chung_m2': chuan_bi_bang_chung_cho_m3(yeu_cau),
    }


# ==================================================
# UC-2.6: KẾT NỐI M2 VỚI SERVICE TẠO TICKET CỦA M3
# Chỉ được gọi khi M3 đã có trong dự án chung
# ==================================================

def tao_ticket_theo_chuan_m3(
    yeu_cau,
    khach_hang,
    danh_muc
):
    # Bước 1: Chuẩn bị dữ liệu từ M2
    du_lieu = chuan_bi_yeu_cau_cho_m3(
        yeu_cau
    )

    # Bước 2: Kiểm tra danh mục Ticket
    if danh_muc is None:
        raise ValueError(
            "Chưa xác định danh mục Ticket của M3."
        )

    # Bước 3: Chỉ import M3 khi thực sự tạo Ticket
    try:
        from tickets.services import create_ticket

    except ModuleNotFoundError as loi:
        if loi.name == 'tickets.services':
            raise RuntimeError(
                "Chưa có service tạo Ticket của M3."
            ) from loi
        raise

    # Bước 4: Gọi đúng service của M3
    ticket = create_ticket(
        khach_hang=khach_hang,
        tieu_de=du_lieu['tieu_de'],
        noi_dung=du_lieu['noi_dung'],
        danh_muc=danh_muc,
        muc_uu_tien=du_lieu['muc_uu_tien'],
        queue=None,
        source_request_id=du_lieu['source_request_id']
    )

    # Bước 5: Trả về Ticket thật
    return ticket

# ==================================================
# UC-2.6: ÁNH XẠ LOẠI VẤN ĐỀ M2 SANG DANH MỤC M3
# Chỉ sử dụng sau khi M3 được tích hợp
# ==================================================

def tim_danh_muc_m3(loai_van_de, bang_anh_xa):

    # Bước 1: Kiểm tra loại vấn đề của M2
    cac_loai_hop_le = {
        'DON_HANG',
        'GIAO_HANG',
        'DOI_TRA',
        'THANH_TOAN',
        'SAN_PHAM_LOI',
        'KHAC',
    }

    if loai_van_de not in cac_loai_hop_le:
        raise ValueError("Loại vấn đề M2 không hợp lệ.")

    # Bước 2: Lấy tên danh mục theo bảng ánh xạ
    if not isinstance(bang_anh_xa, dict):
        raise ValueError("Bảng ánh xạ không hợp lệ.")

    ten_danh_muc = bang_anh_xa.get(loai_van_de)

    if not isinstance(ten_danh_muc, str) or not ten_danh_muc.strip():
        raise ValueError(
            "Chưa cấu hình danh mục M3 cho loại vấn đề này."
        )

    # Bước 3: Chỉ truy cập M3 khi thực sự cần
    from tickets.models import TicketCategory

    danh_muc = TicketCategory.objects.filter(
        ten_danh_muc=ten_danh_muc.strip(),
        dang_hoat_dong=True
    ).first()

    if danh_muc is None:
        raise ValueError(
            "Không tìm thấy danh mục Ticket đang hoạt động."
        )

    return danh_muc

# ================================================
# UC-2.6: CHUẨN BỊ BẰNG CHỨNG M2 CHO M3
# Chưa lưu tệp vào TicketAttachment
# ================================================

def chuan_bi_bang_chung_cho_m3(yeu_cau):
    import re

    if not isinstance(yeu_cau, dict):
        raise ValueError("Bản nháp không hợp lệ.")

    ma_khach_hang = yeu_cau.get('ma_khach_hang')

    if type(ma_khach_hang) is not int or ma_khach_hang <= 0:
        raise ValueError("Thiếu mã khách hàng.")

    bang_chung = yeu_cau.get('bang_chung', [])

    if not isinstance(bang_chung, list) or len(bang_chung) > 5:
        raise ValueError("Danh sách bằng chứng không hợp lệ.")

    ket_qua = []

    for tep in bang_chung:
        if not isinstance(tep, dict):
            raise ValueError("Thông tin tệp không hợp lệ.")

        ten_goc = tep.get('ten_goc')
        duong_dan = tep.get('duong_dan_luu')
        dung_luong = tep.get('dung_luong')

        if not isinstance(ten_goc, str) or not ten_goc.strip():
            raise ValueError("Thiếu tên tệp.")

        if len(ten_goc) > 255:
            raise ValueError("Tên tệp quá dài.")

        mau_duong_dan = (
            rf"kh_{ma_khach_hang}/[0-9a-f]{{32}}\.jpe?g"
        )

        if not isinstance(duong_dan, str) or not re.fullmatch(
            mau_duong_dan, duong_dan
        ):
            raise ValueError("Đường dẫn bằng chứng không hợp lệ.")

        if (
            type(dung_luong) is not int
            or not 0 < dung_luong <= 10 * 1024 * 1024
        ):
            raise ValueError("Dung lượng tệp không hợp lệ.")

        ket_qua.append({
            'ten_goc': ten_goc,
            'duong_dan_luu': duong_dan,
            'dung_luong': dung_luong,
        })

    return ket_qua


# ================================================
# M2 -> M3: DOC BANG CHUNG TU KHO RIENG M2
# ================================================

def mo_bang_chung_m2(*, yeu_cau, khach_hang):
    """
    Mo cac file bang chung da tai len M2.

    Chi tra ve file khi:
    - Ban nhap thuoc dung khach hang.
    - Duong dan dung cau truc duoc phep.
    - File ton tai trong kho rieng M2.
    - Dung luong file thuc te hop le.

    Tra ve danh sach (ten_goc, file_da_mo).
    Ben goi phai dong file sau khi su dung.
    """
    from pathlib import Path

    from django.conf import settings
    from django.core.files.storage import FileSystemStorage
    from django.core.exceptions import ValidationError

    if yeu_cau.get("ma_khach_hang") != khach_hang.pk:
        raise ValidationError(
            "Ban khong co quyen truy cap bang chung nay."
        )

    try:
        danh_sach = chuan_bi_bang_chung_cho_m3(yeu_cau)
    except ValueError as error:
        raise ValidationError(str(error)) from error

    thu_muc_rieng = (
        Path(settings.BASE_DIR).parent
        / "CRM_HULO_m2_private"
    )

    kho_luu = FileSystemStorage(
        location=str(thu_muc_rieng)
    )

    ket_qua = []

    try:
        for thong_tin in danh_sach:
            duong_dan = thong_tin["duong_dan_luu"]

            if not kho_luu.exists(duong_dan):
                raise ValidationError(
                    "Khong tim thay file bang chung M2."
                )

            dung_luong_thuc = kho_luu.size(duong_dan)

            if (
                dung_luong_thuc <= 0
                or dung_luong_thuc > 10 * 1024 * 1024
                or dung_luong_thuc != thong_tin["dung_luong"]
            ):
                raise ValidationError(
                    "Dung luong file bang chung khong hop le."
                )

            tep = kho_luu.open(duong_dan, "rb")

            # Service M3 dung tep.name de kiem tra duoi JPG/JPEG.
            # Vi ten luu M2 la UUID, can truyen ten goc rieng
            # o buoc tich hop tiep theo.
            ket_qua.append(
                {
                    "ten_goc": thong_tin["ten_goc"],
                    "duong_dan_luu": duong_dan,
                    "tep": tep,
                }
            )

        return ket_qua

    except Exception:
        for muc in ket_qua:
            muc["tep"].close()
        raise


# ================================================
# M2 -> M3: CHUAN BI FILE GUI SANG M3
# ================================================

from contextlib import contextmanager
from django.core.files.base import File


@contextmanager
def chuan_bi_file_gui_m3(*, yeu_cau, khach_hang):
    """
    Chuan bi anh cua M2 thanh Django File.

    - Giu nguyen noi dung anh.
    - Su dung ten file goc.
    - Tu dong dong cac file sau khi su dung.
    - Khong tao Ticket hay TicketAttachment.
    """

    danh_sach_da_mo = mo_bang_chung_m2(
        yeu_cau=yeu_cau,
        khach_hang=khach_hang,
    )

    try:
        danh_sach_file = []

        for muc in danh_sach_da_mo:
            tep = File(
                muc["tep"],
                name=muc["ten_goc"],
            )

            danh_sach_file.append(tep)

        yield danh_sach_file

    finally:
        for muc in danh_sach_da_mo:
            muc["tep"].close()
