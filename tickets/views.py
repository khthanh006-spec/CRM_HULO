from accounts.models import Staff
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import role_required

from .models import Ticket, TicketCategory, TicketLog

from .forms import (
    TicketMessageForm,
    TicketResolveForm,
    TicketConfirmationForm,
)


# ==========================================================
# UC-3.2 - TICKET QUEUE / DANH SÁCH TICKET
# ==========================================================

@login_required(login_url='login')
@role_required('CSKH', 'MANAGER', 'ADMIN')
def ticket_home(request):

    tickets = Ticket.objects.select_related(
        'khach_hang',
        'danh_muc',
        'nguoi_phu_trach',
    )

    # CSKH chỉ xem Ticket được giao cho mình
    staff = getattr(request.user, 'staff_profile', None)

    if staff is not None and staff.vai_tro == 'CSKH':
        tickets = tickets.filter(nguoi_phu_trach=staff)

    # Thống kê trước khi lọc
    now = timezone.now()
    warning_limit = now + timedelta(hours=4)

    stats = {
        'cho_tiep_nhan': tickets.filter(
            trang_thai='ASSIGNED'
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

    keyword = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    priority = request.GET.get('priority', '').strip()
    category = request.GET.get('category', '').strip()

    # Tìm kiếm theo mã, tiêu đề, tên khách hàng
    if keyword:
        tickets = tickets.filter(
            Q(ma_ticket__icontains=keyword) |
            Q(tieu_de__icontains=keyword) |
            Q(khach_hang__ho_ten__icontains=keyword)
        )

    # Bộ lọc
    if status in dict(Ticket.STATUS_CHOICES):
        tickets = tickets.filter(trang_thai=status)

    if priority in dict(Ticket.PRIORITY_CHOICES):
        tickets = tickets.filter(muc_uu_tien=priority)

    if category.isdigit():
        tickets = tickets.filter(danh_muc_id=int(category))

    tickets = tickets.order_by('-thoi_diem_tao')


    # UC3.6 - Xác định trạng thái và thời gian SLA cho từng Ticket
    tickets = list(tickets)

    for ticket in tickets:
        ticket.sla_remaining = None

        if ticket.trang_thai in ['RESOLVED', 'CLOSED']:
            ticket.sla_status = 'DONE'

        elif ticket.sla_deadline is None:
            ticket.sla_status = 'NO_SLA'

        else:
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



    categories = TicketCategory.objects.filter(
        dang_hoat_dong=True
    ).order_by('ten_danh_muc')

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

    staff = getattr(request.user, 'staff_profile', None)

    if staff is not None and staff.vai_tro == 'CSKH':
        if ticket.nguoi_phu_trach_id != staff.pk:
            return HttpResponseForbidden(
                "Bạn không có quyền xem Ticket này."
            )

    # Xác định vai trò người đang đăng nhập
    user_role = (
        staff.vai_tro if staff is not None
        else ('ADMIN' if request.user.is_superuser else None)
    )

    # Danh sách nhân viên CSKH để phân công Ticket mới
    staff_options = Staff.objects.none()

    if ticket.trang_thai == 'NEW' and user_role in ('MANAGER', 'ADMIN'):
        staff_options = Staff.objects.filter(
            vai_tro='CSKH'
        ).order_by('ho_ten')

    # ==========================================
    # UC-3.6 - TRẠNG THÁI VÀ THỜI GIAN SLA
    # ==========================================

    now = timezone.now()
    warning_limit = now + timedelta(hours=4)

    ticket.sla_remaining = None

    if ticket.trang_thai in ['RESOLVED', 'CLOSED']:
        ticket.sla_status = 'DONE'

    elif ticket.sla_deadline is None:
        ticket.sla_status = 'NO_SLA'

    else:
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

    # ==========================================
    # LỊCH SỬ XỬ LÝ TICKET
    # ==========================================

    logs = ticket.logs.select_related(
        'nguoi_thuc_hien'
    ).order_by('-thoi_diem')

    ticket_messages = ticket.messages.select_related(
        'nguoi_gui'
    ).order_by('thoi_diem_gui', 'pk')

    # ==========================================
    # DANH SÁCH BẰNG CHỨNG ĐÍNH KÈM
    # ==========================================

    danh_sach_bang_chung = (
        ticket.attachments.all().order_by(
            'thoi_diem_tai_len',
            'pk'
        )
    )

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

        # Cập nhật trạng thái
        ticket.trang_thai = 'IN_PROGRESS'
        ticket.save(
            update_fields=[
                'trang_thai',
                'thoi_diem_cap_nhat',
            ]
        )

        # Ghi lịch sử
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

        # Lưu TicketMessage
        ticket_message = form.save(commit=False)
        ticket_message.ticket = ticket
        ticket_message.nguoi_gui = request.user
        ticket_message.save()

        # Phân biệt PUBLIC và INTERNAL
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

        # Chỉ được hoàn tất Ticket đang xử lý
        if ticket.trang_thai != 'IN_PROGRESS':
            messages.error(
                request,
                "Chỉ có thể hoàn tất Ticket ở trạng thái đang xử lý."
            )
            return redirect('tickets:detail', pk=ticket.pk)



        # UC3.4 - Không hoàn tất Ticket khi chờ thẩm định
        if ticket.trang_thai_tham_dinh == 'WAITING':
            messages.error(
                request,
                "Không thể hoàn tất Ticket vì đang chờ "
                "kết quả thẩm định từ bộ phận chuyên môn."
            )
            return redirect('tickets:detail', pk=ticket.pk)


        # Lưu kết quả
        ticket.ket_qua_xu_ly = form.cleaned_data['ket_qua_xu_ly']

        # Chuyển trạng thái
        ticket.trang_thai = 'RESOLVED'

        # Mỗi lần giải quyết lại, khách hàng sẽ xác nhận lại
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

    # Chỉ cho phép xem Ticket thuộc tài khoản khách hàng
    ticket = get_object_or_404(
        Ticket.objects.select_related('khach_hang').filter(
            khach_hang__ma_tai_khoan=request.user
        ),
        pk=pk
    )

    # Chỉ lấy phản hồi công khai
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
#   RESOLVED + PENDING -> RESOLVED + AGREED
#
# DISAGREE:
#   RESOLVED + PENDING -> REOPENED + DISAGREED
# ==========================================================

@login_required(login_url='login')
@require_POST
def ticket_customer_confirm(request, pk):

    # 1. Chỉ xử lý Ticket thuộc khách hàng đang đăng nhập
    customer_tickets = Ticket.objects.filter(
        khach_hang__ma_tai_khoan=request.user
    )

    ticket = get_object_or_404(customer_tickets, pk=pk)

    # 2. Kiểm tra dữ liệu Form
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

    # 3. Chỉ xác nhận nếu:
    #    - Ticket đang RESOLVED
    #    - Chưa có xác nhận (PENDING)
    #
    # Dùng UPDATE có điều kiện để ngăn xác nhận trùng.
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

    # 4. Thông báo sau khi thực hiện
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

    # 1. Lấy thông tin nhân viên đang đăng nhập
    staff = getattr(request.user, 'staff_profile', None)

    if staff is None or staff.vai_tro != 'CSKH':
        return HttpResponseForbidden(
            "Bạn không có quyền tiếp tục xử lý Ticket."
        )

    # 2. Kiểm tra và cập nhật Ticket trong transaction
    with transaction.atomic():

        ticket = get_object_or_404(
            Ticket.objects.select_for_update(),
            pk=pk
        )

        # 3. Kiểm tra nhân viên được phân công
        if ticket.nguoi_phu_trach_id != staff.pk:
            return HttpResponseForbidden(
                "Ticket này không được phân công cho bạn."
            )

        # 4. Chỉ cho phép tiếp tục Ticket đang REOPENED
        if ticket.trang_thai != 'REOPENED':
            messages.error(
                request,
                "Ticket không ở trạng thái mở lại."
            )

            return redirect(
                'tickets:detail',
                pk=ticket.pk
            )

        # 5. Chuyển REOPENED -> IN_PROGRESS
        ticket.trang_thai = 'IN_PROGRESS'

        ticket.save(
            update_fields=[
                'trang_thai',
                'thoi_diem_cap_nhat',
            ]
        )

        # 6. Lưu lịch sử
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

    # 7. Thông báo thành công
    messages.success(
        request,
        "Ticket đã được chuyển sang trạng thái đang xử lý!"
    )

    return redirect(
        'tickets:detail',
        pk=ticket.pk
    )


# ==========================================================
# UC-3.5 - DONG TICKET
# RESOLVED + AGREED -> CLOSED
# ==========================================================

@login_required(login_url='login')
@role_required('CSKH')
@require_POST
def ticket_close(request, pk):

    # 1. Kiem tra nhan vien dang dang nhap
    staff = getattr(request.user, 'staff_profile', None)

    if staff is None or staff.vai_tro != 'CSKH':
        return HttpResponseForbidden(
            "Ban khong co quyen dong Ticket."
        )

    # 2. Khoa Ticket khi cap nhat
    with transaction.atomic():

        ticket = get_object_or_404(
            Ticket.objects.select_for_update(),
            pk=pk
        )

        # 3. Chi nhan vien duoc phan cong moi duoc dong
        if ticket.nguoi_phu_trach_id != staff.pk:
            return HttpResponseForbidden(
                "Ticket nay khong duoc phan cong cho ban."
            )

        # 4. Ticket phai o trang thai RESOLVED
        if ticket.trang_thai != 'RESOLVED':
            messages.error(
                request,
                "Chi co the dong Ticket da duoc giai quyet."
            )
            return redirect('tickets:detail', pk=ticket.pk)

        # 5. Khach hang phai dong y voi ket qua
        if ticket.trang_thai_xac_nhan != 'AGREED':
            messages.error(
                request,
                "Chua the dong Ticket vi khach hang "
                "chua dong y voi ket qua xu ly."
            )
            return redirect('tickets:detail', pk=ticket.pk)

        # 6. Chuyen RESOLVED -> CLOSED
        ticket.trang_thai = 'CLOSED'
        ticket.thoi_diem_cap_nhat = timezone.now()

        ticket.save(
            update_fields=[
                'trang_thai',
                'thoi_diem_cap_nhat',
            ]
        )

        # 7. Ghi lich su dong Ticket
        TicketLog.objects.create(
            ticket=ticket,
            nguoi_thuc_hien=request.user,
            hanh_dong='DONG TICKET',
            noi_dung=(
                f"Nhan vien {staff.ho_ten} dong Ticket "
                "sau khi khach hang dong y voi ket qua. "
                "Trang thai RESOLVED -> CLOSED."
            )
        )

    # 8. Thong bao thanh cong
    messages.success(
        request,
        "Da dong Ticket thanh cong!"
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

        # Nối M3 với M4: tạo hồ sơ lần đầu hoặc dùng lại hồ sơ
        # đã có cho chính Ticket này.
        from disputes.services import tao_hoac_lay_ho_so

        tao_hoac_lay_ho_so(ticket=ticket)

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
        "Đã ghi nhận yêu cầu thẩm định và tạo hoặc cập nhật "
        "hồ sơ thẩm định."
    )

    return redirect('tickets:detail', pk=ticket.pk)
