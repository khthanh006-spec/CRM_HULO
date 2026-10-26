
"""
MODULE 3 - TICKET ATTACHMENT SERVICE

Chuc nang:
- Luu anh JPEG vao TicketAttachment.
- Kiem tra quyen so huu Ticket.
- Gioi han 10 MB, 20 trieu pixel, toi da 5 tep.
- Nhan dien anh nguon M2 de han che luu trung khi gui lai.
- Khong thay doi trang thai, SLA hay nhan vien phu trach.
"""

import hashlib
import re

from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.db import transaction

from PIL import Image, UnidentifiedImageError

from customers.models import Customer

from .models import Ticket, TicketAttachment


SO_TEP_TOI_DA = 5
DUNG_LUONG_TOI_DA = 10 * 1024 * 1024
SO_PIXEL_TOI_DA = 20_000_000


def luu_anh_bang_chung_ticket(
    *,
    ticket,
    khach_hang,
    tep,
    ma_anh_nguon=None,
):
    """
    Luu mot anh JPEG vao Ticket.

    ma_anh_nguon:
        Ma nhan dien anh cua M2.
        Vi du: kh_1/<uuid32>.jpg

    Neu ma_anh_nguon da duoc luu vao Ticket,
    tra ve ban ghi cu trong truong hop gui lai tuan tu.

    Chu y:
        Co che nay chua bao dam chong trung tuyet doi
        khi co nhieu request ghi dong thoi.
    """

    # ==================================================
    # 1. KIEM TRA KHACH HANG
    # ==================================================

    if (
        not isinstance(khach_hang, Customer)
        or not khach_hang.pk
    ):
        raise ValidationError(
            "Khach hang khong hop le."
        )

    if not Customer.objects.filter(
        pk=khach_hang.pk
    ).exists():
        raise ValidationError(
            "Khong tim thay khach hang."
        )

    # ==================================================
    # 2. KIEM TRA TICKET
    # ==================================================

    if (
        not isinstance(ticket, Ticket)
        or not ticket.pk
    ):
        raise ValidationError(
            "Ticket khong hop le."
        )

    if ticket.khach_hang_id != khach_hang.pk:
        raise ValidationError(
            "Ban khong co quyen dinh kem tep "
            "vao Ticket nay."
        )

    # ==================================================
    # 3. KIEM TRA FILE
    # ==================================================

    if tep is None or not hasattr(tep, "read"):
        raise ValidationError(
            "Khong tim thay tep bang chung."
        )

    ten_goc = Path(
        str(getattr(tep, "name", ""))
    ).name

    if not ten_goc or len(ten_goc) > 255:
        raise ValidationError(
            "Ten tep khong hop le."
        )

    duoi_tep = Path(ten_goc).suffix.lower()

    if duoi_tep not in (".jpg", ".jpeg"):
        raise ValidationError(
            "Chi chap nhan anh JPG/JPEG."
        )

    kich_thuoc = getattr(tep, "size", None)

    if (
        type(kich_thuoc) is not int
        or kich_thuoc <= 0
        or kich_thuoc > DUNG_LUONG_TOI_DA
    ):
        raise ValidationError(
            "Anh phai co dung luong "
            "tu 1 byte den 10 MB."
        )

    # ==================================================
    # 4. KIEM TRA MA ANH NGUON M2
    # ==================================================

    ma_bam_nguon = None

    if ma_anh_nguon is not None:

        if not isinstance(ma_anh_nguon, str):
            raise ValidationError(
                "Ma anh nguon khong hop le."
            )

        mau_duong_dan = (
            rf"kh_{khach_hang.pk}/"
            r"[0-9a-f]{32}\.jpe?g"
        )

        if not re.fullmatch(
            mau_duong_dan,
            ma_anh_nguon,
        ):
            raise ValidationError(
                "Ma anh nguon khong thuoc "
                "khach hang hien tai."
            )

        ma_bam_nguon = hashlib.sha256(
            ma_anh_nguon.encode("utf-8")
        ).hexdigest()

    # ==================================================
    # 5. KIEM TRA NOI DUNG JPEG THAT
    # ==================================================

    try:
        tep.seek(0)

        with Image.open(tep) as anh:

            if anh.format != "JPEG":
                raise ValidationError(
                    "Noi dung tep khong phai JPEG."
                )

            if (
                anh.width * anh.height
                > SO_PIXEL_TOI_DA
            ):
                raise ValidationError(
                    "Anh vuot qua 20 trieu pixel."
                )

            anh.load()

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as error:
        raise ValidationError(
            "Anh JPEG bi loi hoac khong hop le."
        ) from error

    finally:
        tep.seek(0)

    # ==================================================
    # 6. KIEM TRA TICKET TRONG TRANSACTION
    # ==================================================

    with transaction.atomic():

        ticket_hien_tai = (
            Ticket.objects
            .select_for_update()
            .filter(
                pk=ticket.pk,
                khach_hang=khach_hang,
            )
            .first()
        )

        if ticket_hien_tai is None:
            raise ValidationError(
                "Khong tim thay Ticket cua khach hang."
            )

        # ==================================================
        # 7. KIEM TRA ANH NGUON DA LUU
        # ==================================================

        if ma_bam_nguon is not None:

            ten_luu = f"{ma_bam_nguon}.jpg"

            anh_da_co = (
                TicketAttachment.objects
                .filter(
                    ticket=ticket_hien_tai,
                    ma_anh_nguon=ma_bam_nguon,
                )
                .first()
            )

            if anh_da_co is not None:

                if not anh_da_co.tep_dinh_kem.storage.exists(
                    anh_da_co.tep_dinh_kem.name
                ):
                    raise ValidationError(
                        "Anh nguon da co ban ghi "
                        "nhung file luu tru bi thieu."
                    )

                return anh_da_co

        else:
            # Truong hop khong co ma nguon:
            # tao ten ngau nhien nhu service cu.
            ten_luu = (
                f"{uuid4().hex}.jpg"
            )

        # ==================================================
        # 8. GIOI HAN 5 TEP / TICKET
        # ==================================================

        so_tep_hien_tai = (
            TicketAttachment.objects
            .filter(ticket=ticket_hien_tai)
            .count()
        )

        if so_tep_hien_tai >= SO_TEP_TOI_DA:
            raise ValidationError(
                "Ticket chi duoc dinh kem "
                "toi da 5 tep."
            )

        # ==================================================
        # 9. LUU FILE VA DATABASE
        # ==================================================

        tep.seek(0)

        bang_chung = TicketAttachment(
            ticket=ticket_hien_tai,
            ten_tep_goc=ten_goc,
            nguoi_tai_len=khach_hang.ma_tai_khoan,
            ma_anh_nguon=ma_bam_nguon,
        )

        try:
            bang_chung.tep_dinh_kem.save(
                ten_luu,
                File(tep),
                save=False,
            )

            bang_chung.save()

        except Exception:
            # Chi xoa file do thao tac nay vua tao.
            # Khong xoa file thuoc ban ghi da ton tai.
            if bang_chung.tep_dinh_kem.name:
                bang_chung.tep_dinh_kem.delete(
                    save=False
                )

            raise

        return bang_chung