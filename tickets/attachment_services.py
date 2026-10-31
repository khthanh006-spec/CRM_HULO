
"""
MODULE 3 - TICKET ATTACHMENT SERVICE

Chức năng:
- Lưu ảnh JPEG vào TicketAttachment.
- Kiểm tra quyền sở hữu Ticket.
- Giới hạn 10 MB, 20 triệu pixel, tối đa 5 ảnh.
- Nhận diện ảnh nguồn M2 để chống lưu trùng.
- Chỉ ghi file vật lý sau khi transaction database commit.
- Không thay đổi trạng thái, SLA hoặc nhân viên phụ trách.
"""

import hashlib
import re

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from PIL import Image, UnidentifiedImageError

from customers.models import Customer

from .models import Ticket, TicketAttachment


SO_TEP_TOI_DA = 5
DUNG_LUONG_TOI_DA = 10 * 1024 * 1024
SO_PIXEL_TOI_DA = 20_000_000


def _kiem_tra_anh_jpeg(du_lieu):
    """
    Kiểm tra nội dung ảnh JPEG thực tế.
    Không chỉ dựa vào phần mở rộng của file.
    """

    try:
        with Image.open(BytesIO(du_lieu)) as anh:

            if anh.format != "JPEG":
                raise ValidationError(
                    "Nội dung tệp không phải ảnh JPEG."
                )

            if anh.width * anh.height > SO_PIXEL_TOI_DA:
                raise ValidationError(
                    "Ảnh vượt quá 20 triệu pixel."
                )

            anh.verify()

        # Mở lại để kiểm tra khả năng giải mã toàn bộ ảnh.
        with Image.open(BytesIO(du_lieu)) as anh:
            anh.load()

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
    ) as error:
        raise ValidationError(
            "Ảnh JPEG bị lỗi hoặc không hợp lệ."
        ) from error


def _xac_minh_ma_anh_nguon(ma_anh_nguon, khach_hang):
    """
    Kiểm tra mã nhận diện ảnh nguồn từ M2.

    Ví dụ:
        kh_1/<uuid32>.jpg

    Database chỉ lưu SHA256 của mã nguồn,
    không lưu trực tiếp mã đường dẫn từ M2.
    """

    if ma_anh_nguon is None:
        return None

    if not isinstance(ma_anh_nguon, str):
        raise ValidationError(
            "Mã ảnh nguồn không hợp lệ."
        )

    mau_duong_dan = (
        rf"kh_{khach_hang.pk}/"
        r"[0-9a-f]{32}\.jpe?g"
    )

    if not re.fullmatch(mau_duong_dan, ma_anh_nguon):
        raise ValidationError(
            "Mã ảnh nguồn không thuộc khách hàng hiện tại."
        )

    return hashlib.sha256(
        ma_anh_nguon.encode("utf-8")
    ).hexdigest()


def _luu_file_sau_commit(
    *,
    attachment_id,
    ten_file,
    du_lieu,
    storage,
    using,
):
    """
    Callback chạy sau khi transaction database commit.

    Nếu lưu file hoặc cập nhật database thất bại:
    - Thử xóa file vừa tạo.
    - Xóa bản ghi TicketAttachment tương ứng.
    - Phát sinh lỗi để bên gọi biết thao tác thất bại.
    """

    ten_file_da_luu = None

    try:
        ten_file_da_luu = storage.save(
            ten_file,
            ContentFile(du_lieu),
        )

        so_ban_ghi = (
            TicketAttachment.objects
            .using(using)
            .filter(pk=attachment_id)
            .update(tep_dinh_kem=ten_file_da_luu)
        )

        if not so_ban_ghi:
            storage.delete(ten_file_da_luu)
            return

    except Exception:
        # Chỉ xóa file thuộc thao tác vừa thực hiện.
        try:
            if ten_file_da_luu:
                storage.delete(ten_file_da_luu)
            else:
                storage.delete(ten_file)
        finally:
            TicketAttachment.objects.using(using).filter(
                pk=attachment_id
            ).delete()

        raise


def luu_anh_bang_chung_ticket(
    *,
    ticket,
    khach_hang,
    tep,
    ma_anh_nguon=None,
):
    """
    Lưu một ảnh JPEG vào Ticket.

    ma_anh_nguon:
        Mã nhận diện ảnh từ Module 2.
        Để None nếu ảnh được tải trực tiếp từ M3.

    Nếu cùng mã ảnh nguồn đã tồn tại:
        Trả về bản ghi cũ nếu file vẫn tồn tại.

    File vật lý chỉ được lưu sau khi transaction
    database ngoài cùng commit thành công.
    """

    # ==========================================
    # 1. KIỂM TRA CUSTOMER
    # ==========================================

    if (
        not isinstance(khach_hang, Customer)
        or not khach_hang.pk
    ):
        raise ValidationError(
            "Khách hàng không hợp lệ."
        )

    # ==========================================
    # 2. KIỂM TRA TICKET
    # ==========================================

    if (
        not isinstance(ticket, Ticket)
        or not ticket.pk
    ):
        raise ValidationError(
            "Ticket không hợp lệ."
        )

    if ticket.khach_hang_id != khach_hang.pk:
        raise ValidationError(
            "Bạn không có quyền đính kèm tệp vào Ticket này."
        )

    # ==========================================
    # 3. KIỂM TRA FILE
    # ==========================================

    if tep is None or not hasattr(tep, "read"):
        raise ValidationError(
            "Không tìm thấy tệp bằng chứng."
        )

    ten_goc = Path(
        str(getattr(tep, "name", "")).replace("\\", "/")
    ).name

    if not ten_goc or len(ten_goc) > 255:
        raise ValidationError(
            "Tên tệp không hợp lệ."
        )

    duoi_tep = Path(ten_goc).suffix.lower()

    if duoi_tep not in (".jpg", ".jpeg"):
        raise ValidationError(
            "Chỉ chấp nhận ảnh JPG/JPEG."
        )

    try:
        tep.seek(0)
        du_lieu = tep.read()
    except (OSError, ValueError) as error:
        raise ValidationError(
            "Không thể đọc tệp bằng chứng."
        ) from error
    finally:
        try:
            tep.seek(0)
        except (OSError, ValueError):
            pass

    if not isinstance(du_lieu, bytes):
        raise ValidationError(
            "Dữ liệu tệp không hợp lệ."
        )

    kich_thuoc = len(du_lieu)

    if (
        kich_thuoc <= 0
        or kich_thuoc > DUNG_LUONG_TOI_DA
    ):
        raise ValidationError(
            "Ảnh phải có dung lượng từ 1 byte đến 10 MB."
        )

    # ==========================================
    # 4. KIỂM TRA NỘI DUNG JPEG
    # ==========================================

    _kiem_tra_anh_jpeg(du_lieu)

    # ==========================================
    # 5. KIỂM TRA MÃ ẢNH NGUỒN M2
    # ==========================================

    ma_bam_nguon = _xac_minh_ma_anh_nguon(
        ma_anh_nguon,
        khach_hang,
    )

    # ==========================================
    # 6. CHUẨN BỊ STORAGE VÀ DATABASE
    # ==========================================

    using = ticket._state.db or "default"

    storage = TicketAttachment._meta.get_field(
        "tep_dinh_kem"
    ).storage

    # ==========================================
    # 7. LƯU BẢN GHI TRONG TRANSACTION
    # ==========================================

    try:
        with transaction.atomic(using=using):

            ticket_hien_tai = (
                Ticket.objects
                .using(using)
                .select_for_update()
                .filter(
                    pk=ticket.pk,
                    khach_hang_id=khach_hang.pk,
                )
                .first()
            )

            if ticket_hien_tai is None:
                raise ValidationError(
                    "Không tìm thấy Ticket của khách hàng."
                )

            # Kiểm tra ảnh nguồn đã được lưu.
            if ma_bam_nguon is not None:

                anh_da_co = (
                    TicketAttachment.objects
                    .using(using)
                    .filter(
                        ticket=ticket_hien_tai,
                        ma_anh_nguon=ma_bam_nguon,
                    )
                    .first()
                )

                if anh_da_co is not None:

                    if (
                        not anh_da_co.tep_dinh_kem.name
                        or not storage.exists(
                            anh_da_co.tep_dinh_kem.name
                        )
                    ):
                        raise ValidationError(
                            "Ảnh nguồn đã có bản ghi "
                            "nhưng file lưu trữ bị thiếu."
                        )

                    return anh_da_co

            # Giới hạn số lượng ảnh.
            so_tep_hien_tai = (
                TicketAttachment.objects
                .using(using)
                .filter(ticket=ticket_hien_tai)
                .count()
            )

            if so_tep_hien_tai >= SO_TEP_TOI_DA:
                raise ValidationError(
                    "Ticket chỉ được đính kèm tối đa 5 ảnh."
                )

            # Tạo tên file duy nhất.
            ten_luu = (
                f"ticket_attachments/"
                f"{timezone.now():%Y/%m/%d}/"
                f"{uuid4().hex}.jpg"
            )

            # Tạo bản ghi DB trước, chưa ghi file vật lý.
            bang_chung = TicketAttachment(
                ticket=ticket_hien_tai,
                tep_dinh_kem=ten_luu,
                ten_tep_goc=ten_goc,
                nguoi_tai_len=khach_hang.ma_tai_khoan,
                ma_anh_nguon=ma_bam_nguon,
            )

            bang_chung.save(using=using)

            # Chỉ ghi file khi transaction ngoài cùng commit.
            transaction.on_commit(
                lambda: _luu_file_sau_commit(
                    attachment_id=bang_chung.pk,
                    ten_file=ten_luu,
                    du_lieu=du_lieu,
                    storage=storage,
                    using=using,
                ),
                using=using,
            )

            return bang_chung

    except IntegrityError:
        # Xử lý trường hợp hai request gửi cùng mã ảnh.
        if ma_bam_nguon is not None:

            anh_da_co = (
                TicketAttachment.objects
                .using(using)
                .filter(
                    ticket_id=ticket.pk,
                    ma_anh_nguon=ma_bam_nguon,
                )
                .first()
            )

            if anh_da_co is not None:
                if (
                    anh_da_co.tep_dinh_kem.name
                    and storage.exists(
                        anh_da_co.tep_dinh_kem.name
                    )
                ):
                    return anh_da_co

                raise ValidationError(
                    "Ảnh nguồn đã có bản ghi "
                    "nhưng file lưu trữ chưa hoàn tất."
                )

        raise
