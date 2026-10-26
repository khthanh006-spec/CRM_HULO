
from datetime import timedelta
from uuid import uuid4
from .routing import chon_nhan_vien_cskh, tim_queue_san_pham

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import Ticket, TicketMessage, TicketLog

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

    - Chống tạo trùng bằng source_request_id.
    - Kiểm tra khách hàng, danh mục, Queue và SLA.
    - Ghi lịch sử tạo Ticket.
    - Tự phân công CSKH cho danh mục sản phẩm đã cấu hình.
    - Không có CSKH phù hợp thì giữ Ticket ở NEW.
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
            "Danh mục Ticket không hợp lệ "
            "hoặc đã ngừng hoạt động."
        )

    # 6. Kiểm tra Queue do bên gọi truyền vào
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

    # 8. Tạo Ticket và phân công trong một transaction
    try:
        with transaction.atomic():

            now = timezone.now()

            # Ánh xạ đã xác nhận trong dữ liệu demo:
            # Hàng bị lỗi -> CSKH - Sản phẩm.
            #
            # Chưa áp dụng cho các danh mục khác
            # khi nhóm chưa cấu hình quy tắc phân luồng.

            la_danh_muc_san_pham = (
                danh_muc.ten_danh_muc == "Hàng bị lỗi"
            )

            if queue is None and la_danh_muc_san_pham:
                queue = tim_queue_san_pham()

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

            # Ghi lịch sử tạo
            TicketLog.objects.create(
                ticket=ticket,
                nguoi_thuc_hien=None,
                hanh_dong="CREATE",
                noi_dung=(
                    "Ticket được tạo từ yêu cầu nguồn: "
                    f"{source_request_id}"
                ),
            )

            # 9. Tự phân công khi đã xác định đúng
            # danh mục và Queue sản phẩm.
            #
            # Không tự phân công mọi danh mục
            # cho nhân viên CSKH một cách tùy tiện.

            if (
                la_danh_muc_san_pham
                and queue is not None
                and queue.ten_queue == "CSKH - Sản phẩm"
            ):

                nhan_vien = chon_nhan_vien_cskh()

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
                        hanh_dong="PHAN_CONG",
                        noi_dung=(
                            "Hệ thống tự động phân công "
                            f"Ticket cho {nhan_vien.ho_ten}. "
                            "Trạng thái NEW → ASSIGNED."
                        ),
                    )

            return ticket

    except IntegrityError:

        # Nếu hai yêu cầu dùng cùng source_request_id,
        # trả về Ticket đã được tạo trước đó.

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

        # Nếu không phải lỗi trùng source_request_id,
        # giữ nguyên lỗi database để điều tra.
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

        ticket = Ticket.objects.select_for_update().filter(
            ma_ticket=ma_ticket,
            khach_hang=khach_hang,
        ).first()

        if ticket is None:
            raise ValidationError(
                "Không tìm thấy Ticket thuộc tài khoản của bạn."
            )

        if ticket.trang_thai != "IN_PROGRESS":
            raise ValidationError(
                "Chỉ có thể bổ sung thông tin khi Ticket "
                "đang được xử lý."
            )

        # Khách hàng là chủ sở hữu Ticket.
        # Tin nhắn được ghi nhận bằng User của khách hàng.
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
