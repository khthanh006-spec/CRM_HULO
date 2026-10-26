
"""
MODULE 2 -> MODULE 3
Dieu phoi chuyen anh bang chung khi tao Ticket.

M2 so huu ban nhap va anh nguon.
M3 so huu Ticket va TicketAttachment.

Khong thay doi Smart Routing, SLA, Ticket Engine.
"""

from django.core.exceptions import ValidationError

from .services import (
    chuan_bi_file_gui_m3,
    chuan_bi_bang_chung_cho_m3,
    tao_ticket_theo_chuan_m3,
)

from tickets.attachment_services import (
    luu_anh_bang_chung_ticket,
)


def tao_ticket_kem_bang_chung(
    *,
    yeu_cau,
    khach_hang,
    danh_muc,
):
    """
    Tao Ticket va chuyen anh tu M2 sang M3.

    Neu source_request_id da ton tai,
    M3 tra ve Ticket cu.

    Neu luu anh loi:
    - Bao loi cho View.
    - View giu nguyen ban nhap.
    - Co the gui lai de bo sung anh con thieu.
    """

    # 1. Kiem tra metadata bang chung M2
    danh_sach_bang_chung = chuan_bi_bang_chung_cho_m3(
        yeu_cau
    )

    # 2. Mo anh nguon va tu dong dong file khi ket thuc
    with chuan_bi_file_gui_m3(
        yeu_cau=yeu_cau,
        khach_hang=khach_hang,
    ) as danh_sach_file:

        if len(danh_sach_file) != len(
            danh_sach_bang_chung
        ):
            raise ValidationError(
                "So luong anh bang chung khong khop."
            )

        # 3. Su dung service tao Ticket chinh thuc
        # cua M3, khong tu tao Ticket tai M2.
        ticket = tao_ticket_theo_chuan_m3(
            yeu_cau=yeu_cau,
            khach_hang=khach_hang,
            danh_muc=danh_muc,
        )

        # 4. Luu tung anh qua service so huu cua M3
        for thong_tin, tep in zip(
            danh_sach_bang_chung,
            danh_sach_file,
        ):
            try:
                luu_anh_bang_chung_ticket(
                    ticket=ticket,
                    khach_hang=khach_hang,
                    tep=tep,
                    ma_anh_nguon=thong_tin[
                        "duong_dan_luu"
                    ],
                )

            except ValidationError:
                raise

            except Exception as error:
                raise ValidationError(
                    "Khong the luu day du anh bang chung. "
                    "Vui long thu gui lai yeu cau."
                ) from error

        # 5. Chi tra ve sau khi da xu ly het anh
        return ticket
