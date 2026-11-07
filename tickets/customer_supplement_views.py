
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import get_user_role

from .customer_supplement_forms import (
    CustomerTicketSupplementForm,
)
from .models import (
    Ticket,
    TicketAttachment,
    TicketEvidenceRequest,
    TicketLog,
    TicketMessage,
)


# ==========================================================
# KHÁCH HÀNG BỔ SUNG THÔNG TIN VÀ MINH CHỨNG
# ==========================================================

@login_required(login_url="login")
@require_POST
def ticket_customer_supplement(request, pk):
    """
    Khách hàng bổ sung thông tin và minh chứng.

    Quy tắc:
    1. Chỉ tài khoản CUSTOMER được sử dụng.
    2. Chỉ được bổ sung vào Ticket của chính mình.
    3. Ticket phải đang IN_PROGRESS.
    4. Lưu tin nhắn dưới dạng PUBLIC.
    5. Có thể đính kèm tối đa một tệp mỗi lần gửi.
    6. Ghi lịch sử thao tác vào TicketLog.
    7. Không đổi trạng thái hoặc nhân viên phụ trách.
    8. Nếu đáp ứng yêu cầu bổ sung đang chờ,
       cập nhật TicketEvidenceRequest thành FULFILLED.
    """

    # ==========================================
    # 1. KIỂM TRA VAI TRÒ
    # ==========================================

    if get_user_role(request.user) != "CUSTOMER":
        return HttpResponseForbidden(
            "Chỉ khách hàng mới được sử dụng "
            "chức năng bổ sung minh chứng."
        )

    # ==========================================
    # 2. KIỂM TRA QUYỀN SỞ HỮU TICKET
    # ==========================================

    customer_tickets = Ticket.objects.filter(
        khach_hang__ma_tai_khoan=request.user
    )

    ticket = get_object_or_404(
        customer_tickets,
        pk=pk,
    )

    # ==========================================
    # 3. KIỂM TRA TRẠNG THÁI TICKET
    # ==========================================

    if ticket.trang_thai != "IN_PROGRESS":
        messages.error(
            request,
            "Bạn chỉ có thể bổ sung thông tin "
            "khi Ticket đang được xử lý."
        )

        return redirect(
            "tickets:customer_result",
            pk=ticket.pk,
        )

    # ==========================================
    # 4. KIỂM TRA DỮ LIỆU FORM
    # ==========================================

    form = CustomerTicketSupplementForm(
        request.POST,
        request.FILES,
    )

    if not form.is_valid():
        errors = []

        for field_errors in form.errors.values():
            for error in field_errors:
                errors.append(str(error))

        messages.error(
            request,
            "Thông tin bổ sung chưa hợp lệ: "
            + "; ".join(errors)
        )

        return redirect(
            "tickets:customer_result",
            pk=ticket.pk,
        )

    noi_dung = form.cleaned_data["noi_dung"]

    tep_minh_chung = form.cleaned_data.get(
        "tep_minh_chung"
    )

    # ==========================================
    # 5. LƯU DỮ LIỆU
    # ==========================================

    da_hoan_thanh_yeu_cau = False

    with transaction.atomic():

        # Khóa Ticket để tránh xung đột với
        # thao tác xử lý của nhân viên CSKH.
        ticket = get_object_or_404(
            Ticket.objects.select_for_update().filter(
                khach_hang__ma_tai_khoan=request.user
            ),
            pk=pk,
        )

        # Kiểm tra lại trạng thái sau khi khóa.
        if ticket.trang_thai != "IN_PROGRESS":
            messages.error(
                request,
                "Ticket đã thay đổi trạng thái. "
                "Vui lòng tải lại trang để kiểm tra."
            )

            return redirect(
                "tickets:customer_result",
                pk=ticket.pk,
            )

        # ======================================
        # 5.1. LƯU TIN NHẮN CÔNG KHAI
        # ======================================

        tin_nhan_bo_sung = TicketMessage.objects.create(
            ticket=ticket,
            nguoi_gui=request.user,
            loai_tin_nhan="PUBLIC",
            noi_dung=noi_dung,
        )

        # ======================================
        # 5.2. LƯU TỆP MINH CHỨNG
        # ======================================

        attachment_name = None

        if tep_minh_chung is not None:

            attachment = TicketAttachment.objects.create(
                ticket=ticket,
                tep_dinh_kem=tep_minh_chung,
                ten_tep_goc=tep_minh_chung.name,
                nguoi_tai_len=request.user,
            )

            attachment_name = (
                attachment.ten_tep_goc
            )

        # ======================================
        # 5.3. KIỂM TRA YÊU CẦU BỔ SUNG
        # ======================================

        yeu_cau_dang_cho = (
            TicketEvidenceRequest.objects
            .select_for_update()
            .filter(
                ticket=ticket,
                trang_thai="PENDING",
            )
            .order_by(
                "thoi_diem_tao",
                "pk",
            )
            .first()
        )

        if yeu_cau_dang_cho is not None:

            # Nếu yêu cầu bắt buộc có tệp,
            # chỉ hoàn thành khi khách hàng
            # thực sự đã tải lên tệp hợp lệ.
            if yeu_cau_dang_cho.yeu_cau_tep:
                du_dieu_kien = (
                    attachment_name is not None
                )

            # Nếu yêu cầu chỉ cần thông tin,
            # nội dung văn bản hợp lệ là đủ.
            else:
                du_dieu_kien = bool(
                    noi_dung.strip()
                )

            if du_dieu_kien:

                yeu_cau_dang_cho.trang_thai = (
                    "FULFILLED"
                )

                yeu_cau_dang_cho.tin_nhan_phan_hoi = (
                    tin_nhan_bo_sung
                )

                yeu_cau_dang_cho.thoi_diem_hoan_thanh = (
                    timezone.now()
                )

                yeu_cau_dang_cho.save(
                    update_fields=[
                        "trang_thai",
                        "tin_nhan_phan_hoi",
                        "thoi_diem_hoan_thanh",
                    ]
                )

                da_hoan_thanh_yeu_cau = True

        # ======================================
        # 5.4. GHI NHẬT KÝ
        # ======================================

        if attachment_name:
            log_content = (
                "Khách hàng bổ sung thông tin "
                "và tải lên một tệp minh chứng. "
                f"Tên tệp: {attachment_name}"
            )
        else:
            log_content = (
                "Khách hàng bổ sung thông tin "
                "trong quá trình xử lý Ticket."
            )

        if da_hoan_thanh_yeu_cau:
            log_content += (
                " Yêu cầu bổ sung minh chứng "
                "đã chuyển sang FULFILLED."
            )

        elif yeu_cau_dang_cho is not None:
            log_content += (
                " Yêu cầu bổ sung vẫn PENDING "
                "do chưa đáp ứng điều kiện "
                "đính kèm tệp minh chứng."
            )

        TicketLog.objects.create(
            ticket=ticket,
            nguoi_thuc_hien=request.user,
            hanh_dong="KHÁCH HÀNG BỔ SUNG THÔNG TIN",
            noi_dung=log_content,
        )

        # ======================================
        # 5.5. CẬP NHẬT THỜI GIAN
        # ======================================

        ticket.thoi_diem_cap_nhat = timezone.now()

        ticket.save(
            update_fields=[
                "thoi_diem_cap_nhat",
            ]
        )

    # ==========================================
    # 6. THÔNG BÁO THÀNH CÔNG
    # ==========================================

    if da_hoan_thanh_yeu_cau:
        messages.success(
            request,
            "Đã gửi thông tin và minh chứng thành công! "
            "Yêu cầu bổ sung của nhân viên CSKH "
            "đã được ghi nhận là hoàn thành."
        )

    elif (
        yeu_cau_dang_cho is not None
        and yeu_cau_dang_cho.yeu_cau_tep
        and tep_minh_chung is None
    ):
        messages.warning(
            request,
            "Đã gửi nội dung bổ sung thành công. "
            "Tuy nhiên, nhân viên CSKH yêu cầu "
            "bổ sung tệp minh chứng. "
            "Vui lòng tải lên tệp để hoàn thành yêu cầu."
        )

    elif tep_minh_chung is not None:
        messages.success(
            request,
            "Đã gửi thông tin bổ sung và "
            "tệp minh chứng thành công!"
        )

    else:
        messages.success(
            request,
            "Đã gửi thông tin bổ sung thành công!"
        )

    return redirect(
        "tickets:customer_result",
        pk=ticket.pk,
    )
