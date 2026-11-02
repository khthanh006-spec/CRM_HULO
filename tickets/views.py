
from datetime import timedelta

from accounts.models import Staff
from accounts.permissions import role_required

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Ticket, TicketCategory, TicketLog
from .forms import (
    TicketMessageForm,
    TicketResolveForm,
    TicketConfirmationForm,
)


# ==========================================================
# HÀM HỖ TRỢ: XÁC ĐỊNH TRẠNG THÁI VÀ THỜI GIAN SLA
# ==========================================================

def _gan_trang_thai_sla(ticket, now, warning_limit):
    ticket.sla_remaining = None

    if ticket.trang_thai in ['RESOLVED', 'CLOSED']:
        ticket.sla_status = 'DONE'
        return

    if ticket.sla_deadline is None:
        ticket.sla_status = 'NO_SLA'
        return

    delta = ticket.sla_deadline - now
    total_minutes = int(abs(delta.total_seconds()) // 60)

    days, remaining_minutes = divmod(total_minutes, 1440)
    hours, minutes = divmod(remaining_minutes, 60)

    parts = []

    if days:
        parts.append(f"{days} ngày")

    if hours:
        parts.append(f"{hours} giờ")

    if minutes or not parts:
        parts.append(f"{minutes} phút")

    duration_text = " ".join(parts)

    if delta.total_seconds() <= 0:
        ticket.sla_status = 'OVERDUE'
        ticket.sla_remaining = f"Quá hạn {duration_text}"

    elif ticket.sla_deadline <= warning_limit:
        ticket.sla_status = 'WARNING'
        ticket.sla_remaining = f"Còn {duration_text}"

    else:
        ticket.sla_status = 'ON_TIME'
        ticket.sla_remaining = f"Còn {duration_text}"


# ==========================================================
# UC-3.2 - TICKET QUEUE / DANH SÁCH TICKET
# ==========================================================

@login_required(login_url='login')
@role_required('CSKH', 'MANAGER', 'ADMIN')
def ticket_home(request):

    # 1. Lấy danh sách Ticket
    tickets = Ticket.objects.select_related(
        'khach_hang',
        'danh_muc',
        'nguoi_phu_trach',
    )

    # 2. Phân quyền CSKH
    staff = getattr(request.user, 'staff_profile', None)

    if staff is not None and staff.vai_tro == 'CSKH':
        tickets = tickets.filter(
            Q(
                trang_thai='NEW',
                nguoi_phu_trach__isnull=True
            )
            |
            Q(
                nguoi_phu_trach=staff
            )
        )

    # 3. Thống kê Ticket và SLA
    now = timezone.now()
    warning_limit = now + timedelta(hours=4)

    stats = {
        'cho_tiep_nhan': tickets.filter(
            trang_thai__in=['NEW', 'ASSIGNED']
        ).count(),

        'dang_xu_ly': tickets.filter(
            trang_thai='IN_PROGRESS'
        ).count(),

        'sap_qua_sla': tickets.filter(
            sla_deadline__gt=now,
            sla_deadline__lte=warning_limit
        ).exclude(
            trang_thai__in=['RESOLVED', 'CLOSED']
        ).count(),

        'qua_han_sla': tickets.filter(
            sla_deadline__lte=now
        ).exclude(
            trang_thai__in=['RESOLVED', 'CLOSED']
        ).count(),

        'da_giai_quyet': tickets.filter(
            trang_thai='RESOLVED'
        ).count(),
    }

    # 4. Thông tin bộ lọc
    keyword = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    priority = request.GET.get('priority', '').strip()
    category = request.GET.get('category', '').strip()

    # 5. Tìm kiếm Ticket
    if keyword:
        tickets = tickets.filter(
            Q(ma_ticket__icontains=keyword)
            |
            Q(tieu_de__icontains=keyword)
            |
            Q(khach_hang__ho_ten__icontains=keyword)
        )

    # 6. Lọc trạng thái
    if status in dict(Ticket.STATUS_CHOICES):
        tickets = tickets.filter(trang_thai=status)

    # 7. Lọc độ ưu tiên
    if priority in dict(Ticket.PRIORITY_CHOICES):
        tickets = tickets.filter(muc_uu_tien=priority)

    # 8. Lọc danh mục
    if category.isdigit():
        tickets = tickets.filter(
            danh_muc_id=int(category)
        )

    # 9. Sắp xếp mới nhất
    tickets = tickets.order_by('-thoi_diem_tao')

    # 10. Xác định trạng thái và thời gian SLA
    tickets = list(tickets)

    for ticket in tickets:
        _gan_trang_thai_sla(ticket, now, warning_limit)

    # 11. Danh mục Ticket
    categories = TicketCategory.objects.filter(
        dang_hoat_dong=True
    ).order_by('ten_danh_muc')

    # 12. Hiển thị giao diện
    return render(
        request,
        'tickets/home.html',
        {
            'tickets': tickets,
            'stats': stats,
            'categories': categories,
            'keyword': keyword,
            'selected_status': status,
            'selected_priority': priority,
            'selected_category': category,
        }
    )


# ==========================================================
# UC-3.2 - CHI TIẾT TICKET DÀNH CHO NHÂN VIÊN
# ==========================================================

@login_required(login_url='login')
@role_required('CSKH', 'MANAGER', 'ADMIN')
def ticket_detail(request, pk):

    # 1. Lấy thông tin Ticket
    ticket = get_object_or_404(
        Ticket.objects.select_related(
            'khach_hang',
            'danh_muc',
            'queue',
            'nguoi_phu_trach',
            'sla_config',
        ),
        pk=pk
    )

    # 2. Xác định vai trò
    staff = getattr(
        request.user,
        'staff_profile',
        None
    )

    user_role = (
        staff.vai_tro
        if staff is not None
        else (
            'ADMIN'
            if request.user.is_superuser
            else None
        )
    )

    # 3. Kiểm tra quyền xem
    if user_role == 'CSKH':

        ticket_moi_chua_phan_cong = (
            ticket.trang_thai == 'NEW'
            and ticket.nguoi_phu_trach_id is None
        )

        ticket_cua_minh = (
            ticket.nguoi_phu_trach_id == staff.pk
        )

        if not (
            ticket_moi_chua_phan_cong
            or ticket_cua_minh
        ):
            return HttpResponseForbidden(
                "Bạn không có quyền xem Ticket này."
            )

    elif user_role not in ('MANAGER', 'ADMIN'):
        return HttpResponseForbidden(
            "Bạn không có quyền xem Ticket này."
        )

    # 4. Danh sách nhân viên để phân công
    staff_options = Staff.objects.none()

    if (
        ticket.trang_thai == 'NEW'
        and user_role in ('MANAGER', 'ADMIN')
    ):
        staff_options = Staff.objects.filter(
            vai_tro='CSKH'
        ).order_by('ho_ten')

    # 5. Trạng thái và thời gian SLA
    now = timezone.now()
    warning_limit = now + timedelta(hours=4)

    _gan_trang_thai_sla(ticket, now, warning_limit)

    # 6. Lịch sử xử lý Ticket
    logs = ticket.logs.select_related(
        'nguoi_thuc_hien'
    ).order_by('-thoi_diem')

    # 7. Tin nhắn trao đổi
    ticket_messages = ticket.messages.select_related(
        'nguoi_gui'
    ).order_by(
        'thoi_diem_gui',
        'pk'
    )

    # 8. Bằng chứng đính kèm
    danh_sach_bang_chung = (
        ticket.attachments.all().order_by(
            'thoi_diem_tai_len',
            'pk'
        )
    )

    # 9. Hiển thị chi tiết
    return render(
        request,
        'tickets/ticket_detail.html',
        {
            'ticket': ticket,
            'logs': logs,
            'ticket_messages': ticket_messages,
            'message_form': TicketMessageForm(),
            'resolve_form': TicketResolveForm(),
            'user_role': user_role,
            'staff_options': staff_options,
            'danh_sach_bang_chung': danh_sach_bang_chung,
        }
    )


# ==========================================================
# UC-3.2 - TIẾP NHẬN TICKET
# ASSIGNED -> IN_PROGRESS
# ==========================================================

@login_required(login_url='login')
@role_required('CSKH')
@require_POST
def ticket_accept(request, pk):

    staff = getattr(request.user, 'staff_profile', None)

    if staff is None or staff.vai_tro != 'CSKH':
        return HttpResponseForbidden(
            "Bạn không có quyền tiếp nhận Ticket."
        )

    with transaction.atomic():

        ticket = get_object_or_404(
            Ticket.objects.select_for_update(),
            pk=pk
        )

        if ticket.nguoi_phu_trach_id != staff.pk:
            return HttpResponseForbidden(
                "Ticket không được phân công cho bạn."
            )

        if ticket.trang_thai != 'ASSIGNED':
            messages.error(
                request,
                "Ticket không còn ở trạng thái chờ tiếp nhận."
            )
            return redirect('tickets:detail', pk=ticket.pk)

        ticket.trang_thai = 'IN_PROGRESS'
        ticket.save(
            update_fields=[
                'trang_thai',
                'thoi_diem_cap_nhat',
            ]
        )

        TicketLog.objects.create(
            ticket=ticket,
            nguoi_thuc_hien=request.user,
            hanh_dong='TIẾP NHẬN TICKET',
            noi_dung=(
                f"Nhân viên {staff.ho_ten} tiếp nhận Ticket. "
                "Trạng thái ASSIGNED → IN_PROGRESS."
            )
        )

    messages.success(
        request,
        "Tiếp nhận Ticket thành công!"
    )

    return redirect('tickets:detail', pk=ticket.pk)


# ==========================================================
# UC-3.3 - PHẢN HỒI KHÁCH HÀNG / GHI CHÚ NỘI BỘ
# ==========================================================

@login_required(login_url='login')
@role_required('CSKH')
@require_POST
def ticket_add_message(request, pk):

    staff = getattr(request.user, 'staff_profile', None)

    if staff is None or staff.vai_tro != 'CSKH':
        return HttpResponseForbidden(
            "Bạn không có quyền phản hồi Ticket."
        )

    form = TicketMessageForm(request.POST)

    if not form.is_valid():
        messages.error(
            request,
            "Nội dung không hợp lệ. "
            "Vui lòng chọn loại nội dung và nhập phản hồi."
        )
        return redirect('tickets:detail', pk=pk)

    with transaction.atomic():

        ticket = get_object_or_404(
            Ticket.objects.select_for_update(),
            pk=pk
        )

        if ticket.nguoi_phu_trach_id != staff.pk:
            return HttpResponseForbidden(
                "Bạn không được phân công xử lý Ticket này."
            )

        if ticket.trang_thai != 'IN_PROGRESS':
            messages.error(
                request,
                "Chỉ được gửi phản hồi khi Ticket đang xử lý."
            )
            return redirect('tickets:detail', pk=ticket.pk)

        ticket_message = form.save(commit=False)
        ticket_message.ticket = ticket
        ticket_message.nguoi_gui = request.user
        ticket_message.save()

        if ticket_message.loai_tin_nhan == 'PUBLIC':
            hanh_dong = 'PHẢN HỒI KHÁCH HÀNG'
            noi_dung_log = (
                f"Nhân viên {staff.ho_ten} tạo phản hồi công khai."
            )
        else:
            hanh_dong = 'GHI CHÚ NỘI BỘ'
            noi_dung_log = (
                f"Nhân viên {staff.ho_ten} thêm ghi chú nội bộ."
            )

        TicketLog.objects.create(
            ticket=ticket,
            nguoi_thuc_hien=request.user,
            hanh_dong=hanh_dong,
            noi_dung=noi_dung_log
        )

        ticket.thoi_diem_cap_nhat = timezone.now()
        ticket.save(update_fields=['thoi_diem_cap_nhat'])

    messages.success(
        request,
        "Đã lưu phản hồi thành công!"
        if ticket_message.loai_tin_nhan == 'PUBLIC'
        else "Đã lưu ghi chú nội bộ thành công!"
    )

    return redirect('tickets:detail', pk=ticket.pk)


# ==========================================================
# UC-3.5 - HOÀN TẤT XỬ LÝ TICKET
# IN_PROGRESS -> RESOLVED
# ==========================================================

@login_required(login_url='login')
@role_required('CSKH')
@require_POST
def ticket_resolve(request, pk):

    staff = getattr(request.user, 'staff_profile', None)

    if staff is None or staff.vai_tro != 'CSKH':
        return HttpResponseForbidden(
            "Bạn không có quyền hoàn tất Ticket."
        )

    form = TicketResolveForm(request.POST)

    if not form.is_valid():
        messages.error(
            request,
            "Kết quả xử lý không hợp lệ. "
            "Vui lòng nhập ít nhất 10 ký tự."
        )
        return redirect('tickets:detail', pk=pk)

    with transaction.atomic():

        ticket = get_object_or_404(
            Ticket.objects.select_for_update(),
            pk=pk
        )

        if ticket.nguoi_phu_trach_id != staff.pk:
            return HttpResponseForbidden(
                "Ticket này không được phân công cho bạn."
            )

        if ticket.trang_thai != 'IN_PROGRESS':
            messages.error(
                request,
                "Chỉ có thể hoàn tất Ticket ở trạng thái đang xử lý."
            )
            return redirect('tickets:detail', pk=ticket.pk)

        if ticket.trang_thai_tham_dinh == 'WAITING':
            messages.error(
                request,
                "Không thể hoàn tất Ticket vì đang chờ "
                "kết quả thẩm định từ bộ phận chuyên môn."
            )
            return redirect('tickets:detail', pk=ticket.pk)

        ticket.ket_qua_xu_ly = form.cleaned_data['ket_qua_xu_ly']
        ticket.trang_thai = 'RESOLVED'

        ticket.trang_thai_xac_nhan = 'PENDING'
        ticket.ly_do_khong_dong_y = ''
        ticket.thoi_diem_xac_nhan = None

        ticket.save(
            update_fields=[
                'ket_qua_xu_ly',
                'trang_thai',
                'trang_thai_xac_nhan',
                'ly_do_khong_dong_y',
                'thoi_diem_xac_nhan',
                'thoi_diem_cap_nhat',
            ]
        )

        TicketLog.objects.create(
            ticket=ticket,
            nguoi_thuc_hien=request.user,
            hanh_dong='HOÀN TẤT XỬ LÝ',
            noi_dung=(
                f"Nhân viên {staff.ho_ten} hoàn tất Ticket. "
                "Trạng thái IN_PROGRESS → RESOLVED. "
                f"Kết quả: {ticket.ket_qua_xu_ly}"
            )
        )

    messages.success(
        request,
        "Đã hoàn tất xử lý Ticket thành công!"
    )

    return redirect('tickets:detail', pk=ticket.pk)


# ==========================================================
# UC-3.5 - KHÁCH HÀNG XEM KẾT QUẢ XỬ LÝ
# ==========================================================

@login_required(login_url='login')
def ticket_customer_result(request, pk):

    ticket = get_object_or_404(
        Ticket.objects.select_related('khach_hang').filter(
            khach_hang__ma_tai_khoan=request.user
        ),
        pk=pk
    )

    # Chỉ lấy phản hồi công khai, không lộ ghi chú nội bộ
    public_messages = (
        ticket.messages
        .filter(loai_tin_nhan='PUBLIC')
        .select_related('nguoi_gui')
        .order_by('thoi_diem_gui')
    )

    return render(
        request,
        'tickets/customer_result.html',
        {
            'ticket': ticket,
            'confirmation_form': TicketConfirmationForm(),
            'public_messages': public_messages,
        }
    )


# ==========================================================
# UC-3.5 - KHÁCH HÀNG XÁC NHẬN KẾT QUẢ
#
# AGREE:
# RESOLVED + PENDING -> RESOLVED + AGREED
#
# DISAGREE:
# RESOLVED + PENDING -> REOPENED + DISAGREED
# ==========================================================

@login_required(login_url='login')
@require_POST
def ticket_customer_confirm(request, pk):

    customer_tickets = Ticket.objects.filter(
        khach_hang__ma_tai_khoan=request.user
    )

    ticket = get_object_or_404(customer_tickets, pk=pk)

    form = TicketConfirmationForm(request.POST)

    if not form.is_valid():
        messages.error(
            request,
            "Thông tin xác nhận chưa hợp lệ. "
            "Nếu không đồng ý, vui lòng nhập lý do."
        )
        return redirect('tickets:customer_result', pk=ticket.pk)

    lua_chon = form.cleaned_data['lua_chon']
    ly_do = form.cleaned_data['ly_do']
    now = timezone.now()

    with transaction.atomic():

        if lua_chon == 'AGREE':

            updated = customer_tickets.filter(
                pk=pk,
                trang_thai='RESOLVED',
                trang_thai_xac_nhan='PENDING',
            ).update(
                trang_thai_xac_nhan='AGREED',
                ly_do_khong_dong_y='',
                thoi_diem_xac_nhan=now,
                thoi_diem_cap_nhat=now,
            )

            if updated == 1:
                TicketLog.objects.create(
                    ticket=ticket,
                    nguoi_thuc_hien=request.user,
                    hanh_dong='KHÁCH HÀNG ĐỒNG Ý',
                    noi_dung=(
                        "Khách hàng xác nhận đồng ý với "
                        "kết quả xử lý Ticket."
                    )
                )

        elif lua_chon == 'DISAGREE':

            updated = customer_tickets.filter(
                pk=pk,
                trang_thai='RESOLVED',
                trang_thai_xac_nhan='PENDING',
            ).update(
                trang_thai='REOPENED',
                trang_thai_xac_nhan='DISAGREED',
                ly_do_khong_dong_y=ly_do,
                thoi_diem_xac_nhan=now,
                thoi_diem_cap_nhat=now,
            )

            if updated == 1:
                TicketLog.objects.create(
                    ticket=ticket,
                    nguoi_thuc_hien=request.user,
                    hanh_dong='KHÁCH HÀNG YÊU CẦU MỞ LẠI',
                    noi_dung=(
                        "Khách hàng không đồng ý với kết quả. "
                        f"Lý do: {ly_do}. "
                        "Trạng thái RESOLVED → REOPENED."
                    )
                )

    if updated == 0:
        messages.error(
            request,
            "Ticket đã được xác nhận trước đó hoặc "
            "không còn ở trạng thái chờ xác nhận."
        )

    elif lua_chon == 'AGREE':
        messages.success(
            request,
            "HULOECOM đã ghi nhận xác nhận đồng ý của bạn!"
        )

    else:
        messages.success(
            request,
            "Đã ghi nhận yêu cầu xử lý lại. "
            "Ticket được chuyển sang REOPENED."
        )

    return redirect(
        'tickets:customer_result',
        pk=ticket.pk
    )


# ==========================================================
# UC-3.5 - TIẾP TỤC XỬ LÝ TICKET ĐÃ MỞ LẠI
# REOPENED -> IN_PROGRESS
# ==========================================================

@login_required(login_url='login')
@role_required('CSKH')
@require_POST
def ticket_resume(request, pk):

    staff = getattr(request.user, 'staff_profile', None)

    if staff is None or staff.vai_tro != 'CSKH':
        return HttpResponseForbidden(
            "Bạn không có quyền tiếp tục xử lý Ticket."
        )

    with transaction.atomic():

        ticket = get_object_or_404(
            Ticket.objects.select_for_update(),
            pk=pk
        )

        if ticket.nguoi_phu_trach_id != staff.pk:
            return HttpResponseForbidden(
                "Ticket này không được phân công cho bạn."
            )

        if ticket.trang_thai != 'REOPENED':
            messages.error(
                request,
                "Ticket không ở trạng thái mở lại."
            )
            return redirect(
                'tickets:detail',
                pk=ticket.pk
            )

        ticket.trang_thai = 'IN_PROGRESS'

        ticket.save(
            update_fields=[
                'trang_thai',
                'thoi_diem_cap_nhat',
            ]
        )

        TicketLog.objects.create(
            ticket=ticket,
            nguoi_thuc_hien=request.user,
            hanh_dong='TIẾP TỤC XỬ LÝ',
            noi_dung=(
                f"Nhân viên {staff.ho_ten} tiếp tục xử lý "
                "Ticket sau khi khách hàng không đồng ý. "
                "Trạng thái REOPENED → IN_PROGRESS."
            )
        )

    messages.success(
        request,
        "Ticket đã được chuyển sang trạng thái đang xử lý!"
    )

    return redirect(
        'tickets:detail',
        pk=ticket.pk
    )


# ==========================================================
# UC-3.5 - ĐÓNG TICKET
# RESOLVED + AGREED -> CLOSED
# ==========================================================

@login_required(login_url='login')
@role_required('CSKH')
@require_POST
def ticket_close(request, pk):

    staff = getattr(request.user, 'staff_profile', None)

    if staff is None or staff.vai_tro != 'CSKH':
        return HttpResponseForbidden(
            "Bạn không có quyền đóng Ticket."
        )

    with transaction.atomic():

        ticket = get_object_or_404(
            Ticket.objects.select_for_update(),
            pk=pk
        )

        if ticket.nguoi_phu_trach_id != staff.pk:
            return HttpResponseForbidden(
                "Ticket này không được phân công cho bạn."
            )

        if ticket.trang_thai != 'RESOLVED':
            messages.error(
                request,
                "Chỉ có thể đóng Ticket đã được giải quyết."
            )
            return redirect('tickets:detail', pk=ticket.pk)

        if ticket.trang_thai_xac_nhan != 'AGREED':
            messages.error(
                request,
                "Chưa thể đóng Ticket vì khách hàng "
                "chưa đồng ý với kết quả xử lý."
            )
            return redirect('tickets:detail', pk=ticket.pk)

        ticket.trang_thai = 'CLOSED'
        ticket.thoi_diem_cap_nhat = timezone.now()

        ticket.save(
            update_fields=[
                'trang_thai',
                'thoi_diem_cap_nhat',
            ]
        )

        TicketLog.objects.create(
            ticket=ticket,
            nguoi_thuc_hien=request.user,
            hanh_dong='DONG TICKET',
            noi_dung=(
                f"Nhân viên {staff.ho_ten} đóng Ticket "
                "sau khi khách hàng đồng ý với kết quả. "
                "Trạng thái RESOLVED -> CLOSED."
            )
        )

    messages.success(
        request,
        "Đã đóng Ticket thành công!"
    )

    return redirect('tickets:detail', pk=ticket.pk)


# ==========================================================
# UC-3.1 / UC-3.2 - PHÂN CÔNG TICKET
# ==========================================================

@login_required(login_url='login')
@role_required('MANAGER', 'ADMIN')
@require_POST
def ticket_assign(request, pk):

    staff_id = request.POST.get('staff_id')

    if not staff_id or not staff_id.isdigit():
        messages.error(
            request,
            "Vui lòng chọn nhân viên CSKH hợp lệ."
        )
        return redirect('tickets:detail', pk=pk)

    with transaction.atomic():

        ticket = get_object_or_404(
            Ticket.objects.select_for_update(),
            pk=pk
        )

        if ticket.trang_thai != 'NEW':
            messages.error(
                request,
                "Chỉ có thể phân công Ticket ở trạng thái NEW."
            )
            return redirect('tickets:detail', pk=ticket.pk)

        staff = get_object_or_404(
            Staff,
            pk=int(staff_id),
            vai_tro='CSKH'
        )

        ticket.nguoi_phu_trach = staff
        ticket.trang_thai = 'ASSIGNED'

        ticket.save(
            update_fields=[
                'nguoi_phu_trach',
                'trang_thai',
                'thoi_diem_cap_nhat',
            ]
        )

        TicketLog.objects.create(
            ticket=ticket,
            nguoi_thuc_hien=request.user,
            hanh_dong='PHAN_CONG',
            noi_dung=(
                f"Ticket được phân công cho nhân viên "
                f"{staff.ho_ten}. "
                "Trạng thái NEW → ASSIGNED."
            )
        )

    messages.success(
        request,
        f"Đã phân công Ticket cho {staff.ho_ten}."
    )

    return redirect('tickets:detail', pk=ticket.pk)


# ==========================================================
# UC-3.4 - GHI NHẬN YÊU CẦU CHUYỂN THẨM ĐỊNH
# ==========================================================

@login_required(login_url='login')
@role_required('CSKH')
@require_POST
def ticket_request_assessment(request, pk):

    staff = getattr(request.user, 'staff_profile', None)

    if staff is None or staff.vai_tro != 'CSKH':
        return HttpResponseForbidden(
            "Bạn không có quyền yêu cầu thẩm định Ticket."
        )

    ly_do = request.POST.get('ly_do_tham_dinh', '').strip()

    if len(ly_do) < 10:
        messages.error(
            request,
            "Vui lòng nhập lý do thẩm định ít nhất 10 ký tự."
        )
        return redirect('tickets:detail', pk=pk)

    with transaction.atomic():

        ticket = get_object_or_404(
            Ticket.objects.select_for_update(),
            pk=pk
        )

        if ticket.nguoi_phu_trach_id != staff.pk:
            return HttpResponseForbidden(
                "Bạn không được phân công xử lý Ticket này."
            )

        if ticket.trang_thai != 'IN_PROGRESS':
            messages.error(
                request,
                "Chỉ được yêu cầu thẩm định khi Ticket đang xử lý."
            )
            return redirect('tickets:detail', pk=ticket.pk)

        if ticket.trang_thai_tham_dinh == 'WAITING':
            messages.warning(
                request,
                "Ticket đã có yêu cầu thẩm định đang chờ kết quả."
            )
            return redirect('tickets:detail', pk=ticket.pk)

        if ticket.trang_thai_tham_dinh == 'COMPLETED':
            messages.warning(
                request,
                "Ticket đã có kết quả thẩm định. "
                "Việc điều chỉnh phương án sẽ sử dụng hồ sơ M4 cũ."
            )
            return redirect('tickets:detail', pk=ticket.pk)

        now = timezone.now()

        ticket.trang_thai_tham_dinh = 'WAITING'
        ticket.thoi_diem_yeu_cau_tham_dinh = now

        ticket.save(
            update_fields=[
                'trang_thai_tham_dinh',
                'thoi_diem_yeu_cau_tham_dinh',
                'thoi_diem_cap_nhat',
            ]
        )

        TicketLog.objects.create(
            ticket=ticket,
            nguoi_thuc_hien=request.user,
            hanh_dong='YEU_CAU_THAM_DINH',
            noi_dung=(
                f"Nhân viên {staff.ho_ten} ghi nhận "
                f"yêu cầu thẩm định. Lý do: {ly_do}"
            )
        )

    messages.success(
        request,
        "Đã ghi nhận yêu cầu thẩm định. "
        "Ticket đang chờ kết quả từ bộ phận chuyên môn."
    )

    return redirect('tickets:detail', pk=ticket.pk)
