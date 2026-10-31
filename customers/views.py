from uuid import uuid4
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_http_methods

from accounts.permissions import role_required
from tickets.models import Ticket

from .forms import CareInteractionForm, CSATForm, LoyaltyPointForm
from .models import Customer, LoyaltyAccount, CareRecord, CSAT
from django.conf import settings
from django.core.exceptions import PermissionDenied
from .services import change_loyalty_points

# =========================================================
# MODULE 5 - TRANG CHU KHACH HANG
# =========================================================

@role_required('CSKH', 'ASSESSOR', 'MANAGER')
def customer_home(request):
    return render(
        request,
        'customers/home.html'
    )


# =========================================================
# MODULE 5 - DANH SACH VA TIM KIEM KHACH HANG
# =========================================================

@role_required('CSKH', 'MANAGER')
def customer_list(request):

    # 1. Lay tu khoa tim kiem
    keyword = request.GET.get('q', '').strip()

    # 2. Lay danh sach khach hang
    customers = (
        Customer.objects
        .all()
        .order_by('ma_khach_hang')
    )

    # 3. Tim theo ten, email hoac ma khach hang
    if keyword:

        conditions = (
            Q(ho_ten__icontains=keyword) |
            Q(email__icontains=keyword)
        )

        if keyword.isdecimal():
            conditions |= Q(
                ma_khach_hang=int(keyword)
            )

        customers = customers.filter(conditions)

    # 4. Truyen du lieu sang giao dien
    context = {
        'customers': customers,
        'keyword': keyword,
    }

    return render(
        request,
        'customers/customer_list.html',
        context
    )


# =========================================================
# MODULE 5 - HO SO CUSTOMER 360
# =========================================================

@role_required('CSKH', 'MANAGER')
def customer_detail(request, customer_id):

    # 1. Lay thong tin khach hang
    customer = get_object_or_404(
        Customer,
        pk=customer_id
    )

    # 2. Lay tai khoan Loyalty
    loyalty_account = (
        LoyaltyAccount.objects
        .select_related('tier')
        .filter(customer=customer)
        .first()
    )

    # 3. Lay lich su giao dich diem
    if loyalty_account:

        transactions = (
            loyalty_account.transactions
            .all()
            .order_by('-created_at', '-pk')
        )

    else:
        transactions = []

    # 4. Lay lich su cham soc khach hang
    care_records = (
        CareRecord.objects
        .filter(customer=customer)
        .select_related('created_by')
        .order_by('-created_at', '-pk')
    )

    # 5. Lay Ticket that tu Module 3
    ticket_queryset = (
        Ticket.objects
        .filter(khach_hang=customer)
        .order_by('-thoi_diem_tao', '-pk')
    )

    ticket_count = ticket_queryset.count()
    tickets = ticket_queryset[:10]

    # 6. Lay danh gia CSAT gan nhat
    latest_csat = (
        CSAT.objects
        .filter(ticket__khach_hang=customer)
        .select_related('ticket')
        .order_by('-created_at', '-pk')
        .first()
    )
    # MODULE 5 - Lich su danh gia CSAT cua khach hang
    csat_history = (
        CSAT.objects
        .filter(ticket__khach_hang=customer)
        .select_related("ticket")
        .order_by("-created_at", "-pk")
    )

    # 7. Tong hop thong tin Customer 360
    context = {
        'customer': customer,
        'loyalty_account': loyalty_account,
        'transactions': transactions,
        'care_records': care_records,
        'tickets': tickets,
        'ticket_count': ticket_count,
        'latest_csat': latest_csat,
        "csat_history": csat_history,
    }

    return render(
        request,
        'customers/customer_detail.html',
        context
    )


# =========================================================
# MODULE 5 - LUU HOAT DONG CHAM SOC / GHI CHU
# =========================================================

@role_required('CSKH', 'MANAGER')
@require_POST
def add_care_record(request, customer_id):

    # 1. Lay khach hang
    customer = get_object_or_404(
        Customer,
        pk=customer_id
    )

    # 2. Lay thong tin tu bieu mau
    care_type = request.POST.get(
        'care_type',
        CareRecord.CareType.NOTE
    )

    content = (
        request.POST.get('content') or ''
    ).strip()

    # 3. Kiem tra du lieu
    if care_type not in CareRecord.CareType.values:

        messages.error(
            request,
            'Hình thức chăm sóc không hợp lệ.'
        )

    elif not content:

        messages.error(
            request,
            'Vui lòng nhập nội dung chăm sóc.'
        )

    elif len(content) > 500:

        messages.error(
            request,
            'Nội dung không được quá 500 ký tự.'
        )

    else:

        # 4. Luu vao database
        CareRecord.objects.create(
            customer=customer,
            created_by=request.user,
            care_type=care_type,
            content=content
        )

        messages.success(
            request,
            'Đã lưu nội dung chăm sóc thành công.'
        )

    # 5. Quay ve Customer 360
    return redirect(
        'customers:detail',
        customer_id=customer.pk
    )


# =========================================================
# MODULE 5 - CHAM SOC KHACH HANG CO CSAT THAP
# =========================================================

@role_required('CSKH', 'MANAGER')
@require_http_methods(['GET', 'POST'])
def csat_care(request, customer_id):

    # 1. Lay khach hang can cham soc
    customer = get_object_or_404(
        Customer,
        pk=customer_id
    )

    # 2. Xu ly khi nhan vien gui hoat dong cham soc
    if request.method == 'POST':

        form = CareInteractionForm(request.POST)

        if form.is_valid():

            # Tao ban ghi nhung chua luu
            care_record = form.save(commit=False)

            # Gan khach hang
            care_record.customer = customer

            # Gan nhan vien thuc hien
            care_record.created_by = request.user

            # Luu hoat dong cham soc
            care_record.save()

            messages.success(
                request,
                'Đã lưu hoạt động chăm sóc thành công.'
            )

            return redirect(
                'customers:csat_care',
                customer_id=customer.pk
            )

    else:

        # Mac dinh hinh thuc cham soc la Goi dien
        form = CareInteractionForm(
            initial={
                'care_type': CareRecord.CareType.CALL
            }
        )

    # 3. Lay lich su cham soc
    care_records = (
        CareRecord.objects
        .filter(customer=customer)
        .select_related('created_by')
        .order_by('-created_at', '-pk')
    )

    # 4. Lay CSAT moi nhat cua khach hang
    # Ket noi M5 CSAT voi Ticket cua M3
    latest_csat = (
        CSAT.objects
        .filter(ticket__khach_hang=customer)
        .select_related('ticket')
        .order_by('-created_at', '-pk')
        .first()
    )

    # 5. Lay Ticket lien quan den CSAT
    # Khong thay doi du lieu Ticket cua M3
    latest_ticket = (
        latest_csat.ticket
        if latest_csat is not None
        else None
    )

    # 6. Xac dinh CSAT thap
    is_low_csat = (
        latest_csat is not None
        and latest_csat.score <= 3
    )

    # 7. Truyen du lieu sang giao dien
    context = {
        'customer': customer,
        'form': form,
        'care_records': care_records,
        'latest_csat': latest_csat,
        'latest_ticket': latest_ticket,
        'is_low_csat': is_low_csat,
    }

    return render(
        request,
        'customers/csat_care.html',
        context
    )


# =========================================================
# MODULE 5 - KHACH HANG GUI DANH GIA CSAT
# =========================================================

@login_required
@require_http_methods(['GET', 'POST'])
def submit_csat(request, ticket_id):

    # 1. Chi cho phep khach hang danh gia Ticket cua minh
    ticket = get_object_or_404(
        Ticket.objects.select_related(
            'khach_hang',
            'danh_muc',
            'nguoi_phu_trach',
        ),
        pk=ticket_id,
        khach_hang__ma_tai_khoan=request.user,
    )

    # 2. Kiem tra Ticket da duoc danh gia chua
    existing_csat = (
        CSAT.objects
        .filter(ticket=ticket)
        .first()
    )

    # 3. Dieu kien duoc phep danh gia
    # Ticket da xu ly va khach hang da dong y ket qua
    can_rate = (
        ticket.trang_thai in ['RESOLVED', 'CLOSED']
        and ticket.trang_thai_xac_nhan == 'AGREED'
    )

    # 4. Khoi tao form danh gia
    form = CSATForm(request.POST or None)

    # 5. Xu ly khi khach hang gui danh gia
    if (
        request.method == 'POST'
        and existing_csat is None
        and can_rate
    ):

        if form.is_valid():

            # Moi Ticket chi co mot CSAT
            csat, created = CSAT.objects.get_or_create(
                ticket=ticket,
                defaults={
                    'score': form.cleaned_data['score'],
                    'comment': form.cleaned_data.get(
                        'comment',
                        ''
                    ),
                },
            )

            if created:
                messages.success(
                    request,
                    'Cảm ơn bạn đã gửi đánh giá cho HULO!'
                )

            return redirect(
                'customers:submit_csat',
                ticket_id=ticket.pk
            )

    # 6. Truyen thong tin Ticket va CSAT sang giao dien
    context = {
        'ticket': ticket,
        'form': form,
        'existing_csat': existing_csat,
        'can_rate': can_rate,
        'rating_values': ['5', '4', '3', '2', '1'],
        'selected_score': request.POST.get(
            'score',
            ''
        ),
    }

    return render(
        request,
        'customers/csat_form.html',
        context
    )

# =========================================================
# MODULE 5 - TRANG QUAN LY LOYALTY
# =========================================================

@role_required('CSKH', 'MANAGER')
def loyalty_detail(request, customer_id):

    # 1. Lay khach hang
    customer = get_object_or_404(
        Customer,
        pk=customer_id
    )

    # 2. Lay tai khoan Loyalty
    loyalty_account = (
        LoyaltyAccount.objects
        .select_related('tier')
        .filter(customer=customer)
        .first()
    )

    # 3. Lay lich su giao dich diem
    if loyalty_account:

        transactions = (
            loyalty_account.transactions
            .all()
            .order_by('-created_at', '-pk')
        )

    else:
        transactions = []

    # 4. Truyen du lieu sang giao dien
    context = {
        'customer': customer,
        'loyalty_account': loyalty_account,
        'transactions': transactions,
    }

    return render(
        request,
        'customers/loyalty_detail.html',
        context
    )

# =====================================================
# MODULE 5 - GIAO DICH DIEM LOYALTY DEMO
# =====================================================


@role_required('CSKH', 'MANAGER')
@require_http_methods(['GET', 'POST'])
def loyalty_adjust_demo(request, customer_id):

    # Chỉ sử dụng trong môi trường DEMO
    if not settings.DEBUG:
        raise PermissionDenied(
            "Chức năng giao dịch Loyalty DEMO không được bật."
        )

    # 1. Lấy khách hàng
    customer = get_object_or_404(
        Customer,
        pk=customer_id
    )

    # 2. Lấy tài khoản Loyalty
    loyalty_account = get_object_or_404(
        LoyaltyAccount.objects.select_related('tier'),
        customer=customer
    )

    # 3. Tạo form
    if request.method == 'POST':

        # Dùng lại mã đã gửi từ biểu mẫu
        form = LoyaltyPointForm(request.POST)

    else:

        # Mỗi lần mở trang mới sẽ có một mã UUID mới
        form = LoyaltyPointForm(
            initial={
                'idempotency_key': uuid4()
            }
        )

    # 4. Xử lý giao dịch
    if request.method == 'POST' and form.is_valid():

        try:

            change_loyalty_points(
                customer=customer,
                transaction_type=form.cleaned_data[
                    'transaction_type'
                ],
                points=form.cleaned_data['points'],
                description=(
                    "DEMO - " +
                    form.cleaned_data['description']
                ),
                performed_by=request.user,
                idempotency_key=form.cleaned_data[
                    'idempotency_key'
                ]
            )

        except ValueError as error:

            form.add_error(None, str(error))

        else:

            messages.success(
                request,
                "Yêu cầu giao dịch Loyalty đã được xử lý. "
                "Nếu gửi lại cùng mã yêu cầu, "
                "điểm sẽ không thay đổi lần thứ hai."
            )

            return redirect(
                'customers:loyalty_detail',
                customer_id=customer.pk
            )

    # 5. Hiển thị biểu mẫu
    context = {
        'customer': customer,
        'loyalty_account': loyalty_account,
        'form': form,
    }

    return render(
        request,
        'customers/loyalty_adjust_demo.html',
        context
    )
