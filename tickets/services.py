
from datetime import timedelta
from uuid import uuid4

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


def create_ticket(
    *,
    khach_hang,
    tieu_de,
    noi_dung,
    danh_muc,
    muc_uu_tien="MEDIUM",
    queue=None,
    source_request_id,
):
    """
    Tạo Ticket chính thức từ M1/M2.

    - Một mã source_request_id ứng với tối đa một Ticket.
    - Nếu gửi lại cùng yêu cầu, trả về Ticket đã tồn tại.
    - Không cho Customer khác dùng lại mã yêu cầu.
    - Tự gắn SLA và ghi TicketLog.
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

    # 2. Kiểm tra Customer
    if (
        not isinstance(khach_hang, Customer)
        or not khach_hang.pk
        or not Customer.objects.filter(pk=khach_hang.pk).exists()
    ):
        raise ValidationError("Khách hàng không hợp lệ.")

    # 3. Kiểm tra yêu cầu đã tồn tại
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

    if muc_uu_tien not in dict(Ticket.PRIORITY_CHOICES):
        raise ValidationError("Mức ưu tiên không hợp lệ.")

    # 5. Kiểm tra danh mục
    if (
        not isinstance(danh_muc, TicketCategory)
        or not danh_muc.pk
        or not TicketCategory.objects.filter(
            pk=danh_muc.pk,
            dang_hoat_dong=True,
        ).exists()
    ):
        raise ValidationError(
            "Danh mục Ticket không hợp lệ hoặc đã ngừng hoạt động."
        )

    # 6. Kiểm tra hàng đợi
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

    # 7. Xác định SLA
    sla = SLAConfig.objects.filter(
        danh_muc=danh_muc,
        muc_uu_tien=muc_uu_tien,
        dang_hoat_dong=True,
    ).first()

    if sla is None:
        raise ValidationError(
            "Chưa có SLA đang hoạt động cho danh mục "
            "và mức ưu tiên này."
        )

    # 8. Tạo Ticket trong transaction riêng
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
                sla_deadline=now + timedelta(
                    hours=sla.thoi_han_gio
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

            return ticket

    except IntegrityError:
        # Trường hợp một yêu cầu khác vừa tạo cùng source ID
        existing_ticket = Ticket.objects.filter(
            source_request_id=source_request_id
        ).first()

        if existing_ticket is not None:
            if existing_ticket.khach_hang_id != khach_hang.pk:
                raise ValidationError(
                    "Mã yêu cầu nguồn đã thuộc về khách hàng khác."
                )

            return existing_ticket

        # Nếu lỗi database không phải do source ID trùng,
        # giữ nguyên lỗi để xử lý đúng nguyên nhân.
        raise
