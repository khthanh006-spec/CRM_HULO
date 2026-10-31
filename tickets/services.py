
from datetime import timedelta
from uuid import uuid4
import unicodedata

from .models import TicketClassificationRule, TicketCategoryQueue
from django.db.models import Count, Q
from accounts.models import Staff

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from customers.models import Customer

from .models import (
    Ticket,
    TicketCategory,
    TicketQueue,
    SLAConfig,
    TicketLog,
)

def chuan_hoa_van_ban(van_ban):
    """
    Chuẩn hóa nội dung để nhận diện từ khóa
    không phân biệt chữ hoa, chữ thường và dấu tiếng Việt.
    """
    van_ban = (van_ban or "").lower().replace("đ", "d")

    return "".join(
        ky_tu
        for ky_tu in unicodedata.normalize("NFD", van_ban)
        if unicodedata.category(ky_tu) != "Mn"
    )



def tu_dong_phan_loai_ticket(tieu_de, noi_dung):
    """
    UC-3.1: Tự động nhận diện Category và Priority
    bằng cách đánh giá toàn bộ quy tắc phân loại.

    - Không phân biệt chữ hoa, chữ thường và dấu tiếng Việt.
    - Đánh giá tất cả từ khóa phù hợp.
    - Ưu tiên cụm từ cụ thể hơn.
    - Tổng hợp điểm theo từng danh mục.
    - Chọn Priority từ quy tắc phù hợp nhất.
    """

    van_ban = chuan_hoa_van_ban(
        f"{tieu_de or ''} {noi_dung or ''}"
    ).strip()

    if not van_ban:
        return None, None

    quy_tac = (
        TicketClassificationRule.objects
        .select_related("danh_muc")
        .filter(
            dang_hoat_dong=True,
            danh_muc__dang_hoat_dong=True,
        )
        .order_by("do_uu_tien_quy_tac", "pk")
    )

    diem_theo_danh_muc = {}

    for rule in quy_tac:

        tu_khoa = chuan_hoa_van_ban(
            rule.tu_khoa
        ).strip()

        if not tu_khoa or tu_khoa not in van_ban:
            continue

        so_lan = van_ban.count(tu_khoa)

        # Ưu tiên cụm từ nhận diện cụ thể.
        diem = len(tu_khoa) ** 2 * min(so_lan, 3)

        category_id = rule.danh_muc_id

        if category_id not in diem_theo_danh_muc:
            diem_theo_danh_muc[category_id] = {
                "danh_muc": rule.danh_muc,
                "tong_diem": 0,
                "diem_tot_nhat": -1,
                "quy_tac_tot_nhat": None,
            }

        ket_qua = diem_theo_danh_muc[category_id]

        ket_qua["tong_diem"] += diem

        quy_tac_cu = ket_qua["quy_tac_tot_nhat"]

        if (
            diem > ket_qua["diem_tot_nhat"]
            or (
                diem == ket_qua["diem_tot_nhat"]
                and (
                    quy_tac_cu is None
                    or rule.do_uu_tien_quy_tac
                    < quy_tac_cu.do_uu_tien_quy_tac
                )
            )
        ):
            ket_qua["diem_tot_nhat"] = diem
            ket_qua["quy_tac_tot_nhat"] = rule

    if not diem_theo_danh_muc:
        return None, None

    ket_qua_cuoi = max(
        diem_theo_danh_muc.values(),
        key=lambda item: (
            item["tong_diem"],
            item["diem_tot_nhat"],
            -item["quy_tac_tot_nhat"].do_uu_tien_quy_tac,
            -item["danh_muc"].pk,
        ),
    )

    rule_tot_nhat = ket_qua_cuoi["quy_tac_tot_nhat"]

    return (
        ket_qua_cuoi["danh_muc"],
        rule_tot_nhat.muc_uu_tien,
    )


def chon_cskh_it_ticket_nhat():
    """
    UC-3.1: Chọn nhân viên CSKH đang sẵn sàng
    và có ít Ticket đang mở nhất.

    Ticket đang mở:
    ASSIGNED, IN_PROGRESS, REOPENED.
    """

    nhan_vien = (
        Staff.objects
        .filter(
            vai_tro="CSKH",
            san_sang_nhan_viec=True,
            ma_tai_khoan__is_active=True,
        )
        .annotate(
            so_ticket_dang_mo=Count(
                "tickets_duoc_giao",
                filter=Q(
                    tickets_duoc_giao__trang_thai__in=[
                        "ASSIGNED",
                        "IN_PROGRESS",
                        "REOPENED",
                    ]
                ),
            )
        )
        .order_by("so_ticket_dang_mo", "ma_nhan_vien")
        .first()
    )

    return nhan_vien



def create_ticket(
    *,
    khach_hang,
    tieu_de,
    noi_dung,
    source_request_id,
    danh_muc=None,
    muc_uu_tien=None,
    queue=None,
):
    """
    UC-3.1: Tạo Ticket từ yêu cầu đã xác nhận.

    M3 tự phân loại Category, Priority, Queue, SLA
    và phân công CSKH có ít Ticket đang mở nhất.

    Nếu thiếu cấu hình hoặc nhân viên phù hợp:
    giữ Ticket ở trạng thái NEW.
    """

    # 1. Kiểm tra mã yêu cầu nguồn
    if not isinstance(source_request_id, str):
        raise ValidationError("Mã yêu cầu nguồn phải là chuỗi.")

    source_request_id = source_request_id.strip()

    if not source_request_id:
        raise ValidationError("Thiếu mã yêu cầu nguồn.")

    if len(source_request_id) > 100:
        raise ValidationError(
            "Mã yêu cầu nguồn không được vượt quá 100 ký tự."
        )

    # 2. Kiểm tra khách hàng
    if (
        not isinstance(khach_hang, Customer)
        or not khach_hang.pk
        or not Customer.objects.filter(
            pk=khach_hang.pk
        ).exists()
    ):
        raise ValidationError("Khách hàng không hợp lệ.")

    # 3. Chống tạo Ticket trùng
    existing_ticket = Ticket.objects.filter(
        source_request_id=source_request_id
    ).first()

    if existing_ticket is not None:
        if existing_ticket.khach_hang_id != khach_hang.pk:
            raise ValidationError(
                "Mã yêu cầu nguồn đã thuộc về khách hàng khác."
            )

        return existing_ticket

    # 4. Kiểm tra nội dung
    if not isinstance(tieu_de, str) or not tieu_de.strip():
        raise ValidationError("Tiêu đề không được để trống.")

    if not isinstance(noi_dung, str) or not noi_dung.strip():
        raise ValidationError("Nội dung không được để trống.")

    tieu_de = tieu_de.strip()
    noi_dung = noi_dung.strip()

    if len(tieu_de) > 255:
        raise ValidationError("Tiêu đề tối đa 255 ký tự.")

    # 5. M3 tự phân loại, không phụ thuộc M1/M2
    danh_muc, muc_uu_tien = tu_dong_phan_loai_ticket(
        tieu_de, noi_dung
    )

    # 6. Xác định Queue
    queue = None

    if danh_muc is not None:
        mapping = (
            TicketCategoryQueue.objects
            .select_related("queue")
            .filter(
                danh_muc=danh_muc,
                queue__dang_hoat_dong=True,
            )
            .first()
        )

        if mapping is not None:
            queue = mapping.queue

    # 7. Xác định SLA
    sla = None

    if danh_muc is not None and muc_uu_tien is not None:
        sla = SLAConfig.objects.filter(
            danh_muc=danh_muc,
            muc_uu_tien=muc_uu_tien,
            dang_hoat_dong=True,
        ).first()

    # 8. Tạo Ticket và phân công trong một transaction
    try:
        with transaction.atomic():
            now = timezone.now()

            ticket = Ticket.objects.create(
                ma_ticket=(
                    f"TK{now.strftime('%Y%m%d')}"
                    f"{uuid4().hex[:10].upper()}"
                ),
                source_request_id=source_request_id,
                khach_hang=khach_hang,
                tieu_de=tieu_de,
                noi_dung=noi_dung,
                danh_muc=danh_muc,
                muc_uu_tien=muc_uu_tien,
                trang_thai="NEW",
                queue=queue,
                sla_config=sla,
                sla_deadline=(
                    now + timedelta(hours=sla.thoi_han_gio)
                    if sla is not None
                    else None
                ),
            )

            TicketLog.objects.create(
                ticket=ticket,
                nguoi_thuc_hien=None,
                hanh_dong="CREATE",
                noi_dung=(
                    "Ticket được tạo từ yêu cầu nguồn: "
                    f"{source_request_id}"
                ),
            )

            # 9. Chỉ phân công khi đã đủ Category,
            # Priority, Queue và SLA.
            if (
                danh_muc is not None
                and muc_uu_tien is not None
                and queue is not None
                and sla is not None
            ):
                nhan_vien = chon_cskh_it_ticket_nhat()

                if nhan_vien is not None:
                    ticket.nguoi_phu_trach = nhan_vien
                    ticket.trang_thai = "ASSIGNED"

                    ticket.save(
                        update_fields=[
                            "nguoi_phu_trach",
                            "trang_thai",
                            "thoi_diem_cap_nhat",
                        ]
                    )

                    TicketLog.objects.create(
                        ticket=ticket,
                        nguoi_thuc_hien=None,
                        hanh_dong="PHAN_CONG_TU_DONG",
                        noi_dung=(
                            "Hệ thống tự động phân công Ticket "
                            f"cho nhân viên {nhan_vien.ho_ten} "
                            "theo số lượng Ticket đang mở."
                        ),
                    )

            # 10. Ghi nhận lý do chờ xử lý thủ công
            if ticket.trang_thai == "NEW":
                ly_do = []

                if danh_muc is None:
                    ly_do.append(
                        "Chưa nhận diện được danh mục và mức ưu tiên"
                    )
                else:
                    if queue is None:
                        ly_do.append(
                            "Chưa có Queue phù hợp"
                        )

                    if sla is None:
                        ly_do.append(
                            "Chưa có cấu hình SLA phù hợp"
                        )

                    if (
                        queue is not None
                        and sla is not None
                    ):
                        ly_do.append(
                            "Chưa có nhân viên CSKH sẵn sàng"
                        )

                TicketLog.objects.create(
                    ticket=ticket,
                    nguoi_thuc_hien=None,
                    hanh_dong="CHO_PHAN_CONG",
                    noi_dung="; ".join(ly_do),
                )

            return ticket

    except IntegrityError:
        # Giữ cơ chế chống tạo Ticket trùng
        # khi có yêu cầu đồng thời.
        existing_ticket = Ticket.objects.filter(
            source_request_id=source_request_id
        ).first()

        if existing_ticket is not None:
            if existing_ticket.khach_hang_id != khach_hang.pk:
                raise ValidationError(
                    "Mã yêu cầu nguồn đã thuộc về khách hàng khác."
                )

            return existing_ticket

        raise

