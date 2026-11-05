
from datetime import timedelta
from uuid import uuid4
import unicodedata

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import Staff
from customers.models import Customer

from .models import (
    Ticket,
    TicketCategory,
    TicketCategoryQueue,
    TicketClassificationRule,
    SLAConfig,
    TicketMessage,
    TicketLog,
)


def chuan_hoa_van_ban(van_ban):
    """
    Chuẩn hóa tiếng Việt để tìm từ khóa.
    Không phân biệt chữ hoa, chữ thường và dấu.
    """
    van_ban = (van_ban or "").lower().replace("đ", "d")

    return "".join(
        ky_tu
        for ky_tu in unicodedata.normalize("NFD", van_ban)
        if unicodedata.category(ky_tu) != "Mn"
    )


def tu_dong_phan_loai_ticket(tieu_de, noi_dung):
    """
    Phân loại Ticket theo quy tắc M3.

    - Tính điểm tất cả từ khóa phù hợp.
    - Ưu tiên cụm từ cụ thể hơn.
    - Chọn danh mục có tổng điểm cao nhất.
    - Lấy mức ưu tiên từ quy tắc phù hợp nhất.
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
        tu_khoa = chuan_hoa_van_ban(rule.tu_khoa).strip()

        if not tu_khoa or tu_khoa not in van_ban:
            continue

        so_lan = van_ban.count(tu_khoa)
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

    return (
        ket_qua_cuoi["danh_muc"],
        ket_qua_cuoi["quy_tac_tot_nhat"].muc_uu_tien,
    )


def xac_dinh_muc_uu_tien(
    *,
    danh_muc,
    tieu_de,
    noi_dung,
    muc_uu_tien_mac_dinh="MEDIUM",
):
    """
    Xác định Priority trong danh mục đã chọn.

    Không cho quy tắc thuộc danh mục khác
    ghi đè danh mục do M2 truyền sang.
    """
    van_ban = chuan_hoa_van_ban(
        f"{tieu_de} {noi_dung}"
    ).strip()

    quy_tac = (
        TicketClassificationRule.objects
        .filter(
            danh_muc=danh_muc,
            dang_hoat_dong=True,
        )
        .order_by("do_uu_tien_quy_tac", "pk")
    )

    quy_tac_phu_hop = []

    for rule in quy_tac:
        tu_khoa = chuan_hoa_van_ban(rule.tu_khoa).strip()

        if tu_khoa and tu_khoa in van_ban:
            diem = (
                len(tu_khoa) ** 2
                * min(van_ban.count(tu_khoa), 3)
            )

            quy_tac_phu_hop.append((diem, rule))

    if quy_tac_phu_hop:
        _, rule_tot_nhat = max(
            quy_tac_phu_hop,
            key=lambda item: (
                item[0],
                -item[1].do_uu_tien_quy_tac,
                -item[1].pk,
            ),
        )

        return rule_tot_nhat.muc_uu_tien

    return muc_uu_tien_mac_dinh


def chon_cskh_it_ticket_nhat():
    """
    Chọn nhân viên CSKH sẵn sàng
    có ít Ticket đang mở nhất.

    Ticket đang mở:
    ASSIGNED, IN_PROGRESS, REOPENED.
    """
    return (
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
    Tạo Ticket chính thức từ M1/M2 hoặc M3.

    Quy tắc tích hợp:
    - Ưu tiên danh mục hợp lệ do M2 truyền sang.
    - Không có danh mục thì M3 tự phân loại.
    - Priority theo quy tắc của danh mục đã chọn.
    - Queue lấy từ TicketCategoryQueue.
    - SLA lấy từ SLAConfig.
    - Tự phân công CSKH ít Ticket đang mở nhất.
    - Thiếu cấu hình thì giữ NEW.
    - Chống tạo trùng bằng source_request_id.
    """

    # 1. Kiểm tra mã yêu cầu nguồn
    if not isinstance(source_request_id, str):
        raise ValidationError(
            "Mã yêu cầu nguồn phải là chuỗi."
        )

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

    # 5. Xác định danh mục
    if danh_muc is not None:
        if (
            not isinstance(danh_muc, TicketCategory)
            or not danh_muc.pk
            or not TicketCategory.objects.filter(
                pk=danh_muc.pk,
                dang_hoat_dong=True,
            ).exists()
        ):
            raise ValidationError(
                "Danh mục Ticket không hợp lệ "
                "hoặc đã ngừng hoạt động."
            )

        # Ưu tiên danh mục do M2 cung cấp.
        muc_uu_tien = xac_dinh_muc_uu_tien(
            danh_muc=danh_muc,
            tieu_de=tieu_de,
            noi_dung=noi_dung,
            muc_uu_tien_mac_dinh=(
                muc_uu_tien or "MEDIUM"
            ),
        )

    else:
        # Không có danh mục: M3 tự phân loại.
        danh_muc, muc_uu_tien_tu_dong = (
            tu_dong_phan_loai_ticket(
                tieu_de,
                noi_dung,
            )
        )

        if muc_uu_tien_tu_dong is not None:
            muc_uu_tien = muc_uu_tien_tu_dong
        else:
            muc_uu_tien = muc_uu_tien or "MEDIUM"

    if muc_uu_tien not in dict(Ticket.PRIORITY_CHOICES):
        raise ValidationError("Mức ưu tiên không hợp lệ.")

    # 6. Xác định Queue từ cấu hình M3
    queue_phu_hop = None

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
            queue_phu_hop = mapping.queue

    # Kiểm tra Queue nếu bên gọi truyền vào.
    if queue is not None:
        if (
            not isinstance(queue, TicketQueue)
            or not queue.pk
            or not TicketQueue.objects.filter(
                pk=queue.pk,
                dang_hoat_dong=True,
            ).exists()
        ):
            raise ValidationError(
                "Queue không hợp lệ hoặc đã ngừng hoạt động."
            )

        if (
            queue_phu_hop is not None
            and queue.pk != queue_phu_hop.pk
        ):
            raise ValidationError(
                "Queue không phù hợp với danh mục Ticket."
            )

    # Queue cuối cùng do M3 xác định.
    queue = queue_phu_hop

    # 7. Xác định SLA
    sla = None

    if danh_muc is not None:
        sla = SLAConfig.objects.filter(
            danh_muc=danh_muc,
            muc_uu_tien=muc_uu_tien,
            dang_hoat_dong=True,
        ).first()

    # 8. Tạo Ticket trong transaction
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

            # 9. Ghi lịch sử tạo Ticket
            TicketLog.objects.create(
                ticket=ticket,
                nguoi_thuc_hien=None,
                hanh_dong="CREATE",
                noi_dung=(
                    "Ticket được tạo từ yêu cầu nguồn: "
                    f"{source_request_id}"
                ),
            )

            # 10. Tự động phân công khi đủ cấu hình
            if (
                danh_muc is not None
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
                            "Hệ thống tự động phân công "
                            f"Ticket cho {nhan_vien.ho_ten}. "
                            f"Queue: {queue.ten_queue}. "
                            "Trạng thái NEW → ASSIGNED."
                        ),
                    )

            # 11. Ghi lý do nếu chờ phân công
            if ticket.trang_thai == "NEW":
                ly_do = []

                if danh_muc is None:
                    ly_do.append(
                        "Chưa nhận diện được danh mục"
                    )

                if queue is None:
                    ly_do.append(
                        "Chưa có Queue phù hợp"
                    )

                if sla is None:
                    ly_do.append(
                        "Chưa có cấu hình SLA phù hợp"
                    )

                if (
                    danh_muc is not None
                    and queue is not None
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
        existing_ticket = Ticket.objects.filter(
            source_request_id=source_request_id
        ).first()

        if existing_ticket is not None:
            if existing_ticket.khach_hang_id != khach_hang.pk:
                raise ValidationError(
                    "Mã yêu cầu nguồn đã thuộc về "
                    "khách hàng khác."
                )

            return existing_ticket

        raise


def bo_sung_thong_tin_ticket(
    *,
    ma_ticket,
    khach_hang,
    noi_dung,
):
    """
    Khách hàng bổ sung thông tin vào Ticket hiện có.

    - Không tạo Ticket mới.
    - Chỉ cho phép khách hàng sở hữu Ticket.
    - Chỉ bổ sung khi Ticket đang IN_PROGRESS.
    - Lưu TicketMessage PUBLIC và TicketLog.
    - Không thay đổi SLA hay người phụ trách.
    """

    if (
        not isinstance(ma_ticket, str)
        or not ma_ticket.strip()
    ):
        raise ValidationError(
            "Vui lòng cung cấp mã Ticket."
        )

    if (
        not isinstance(khach_hang, Customer)
        or not khach_hang.pk
    ):
        raise ValidationError(
            "Thông tin khách hàng không hợp lệ."
        )

    if (
        not isinstance(noi_dung, str)
        or not 10 <= len(noi_dung.strip()) <= 2000
    ):
        raise ValidationError(
            "Nội dung bổ sung phải có từ 10 đến 2000 ký tự."
        )

    noi_dung = noi_dung.strip()
    ma_ticket = ma_ticket.strip()

    with transaction.atomic():
        ticket = (
            Ticket.objects
            .select_for_update()
            .filter(
                ma_ticket=ma_ticket,
                khach_hang=khach_hang,
            )
            .first()
        )

        if ticket is None:
            raise ValidationError(
                "Không tìm thấy Ticket thuộc tài khoản của bạn."
            )

        if ticket.trang_thai != "IN_PROGRESS":
            raise ValidationError(
                "Chỉ có thể bổ sung thông tin khi Ticket "
                "đang được xử lý."
            )

        user = khach_hang.ma_tai_khoan

        tin_nhan = TicketMessage.objects.create(
            ticket=ticket,
            nguoi_gui=user,
            loai_tin_nhan="PUBLIC",
            noi_dung=noi_dung,
        )

        TicketLog.objects.create(
            ticket=ticket,
            nguoi_thuc_hien=user,
            hanh_dong="BO_SUNG_THONG_TIN",
            noi_dung=(
                "Khách hàng đã bổ sung thông tin "
                "trong quá trình xử lý Ticket."
            ),
        )

        return tin_nhan
