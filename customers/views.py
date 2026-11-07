
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from accounts.permissions import role_required
from tickets.models import Ticket

from .forms import (
    CareInteractionForm,
    CSATForm,
    LoyaltyVoucherTransactionForm,
)
from .models import (
    CareRecord,
    CSAT,
    Customer,
    LoyaltyAccount,
    LoyaltyRedemption,
    LoyaltyReward,
    LoyaltyTier,
)
from .order_360 import get_customer_order_360
from .services import change_loyalty_points, redeem_loyalty_voucher


# =========================================================
# MODULE 5 - TRANG CHỦ KHÁCH HÀNG
# =========================================================

@role_required('CSKH', 'ASSESSOR', 'MANAGER')
def customer_home(request):
    return render(request, 'customers/home.html')


# =========================================================
# MODULE 5 - DANH SÁCH VÀ TÌM KIẾM KHÁCH HÀNG
# =========================================================

@role_required('CSKH', 'MANAGER')
def customer_list(request):
    keyword = request.GET.get('q', '').strip()

    customers = (
        Customer.objects
        .all()
        .order_by('ma_khach_hang')
    )

    if keyword:
        conditions = (
            Q(ho_ten__icontains=keyword)
            | Q(email__icontains=keyword)
        )

        if keyword.isdecimal():
            conditions |= Q(ma_khach_hang=int(keyword))

        customers = customers.filter(conditions)

    return render(
        request,
        'customers/customer_list.html',
        {
            'customers': customers,
            'keyword': keyword,
        },
    )


# =========================================================
# HÀM DÙNG CHUNG - TIẾN ĐỘ NÂNG HẠNG LOYALTY
# =========================================================

def get_loyalty_progress(loyalty_account):
    if not loyalty_account:
        return None

    total_points = loyalty_account.total_points_earned

    tiers = LoyaltyTier.objects.order_by(
        'min_total_points',
        'pk',
    )

    reached_tier = None
    next_tier = None

    for tier in tiers:
        if tier.min_total_points <= total_points:
            reached_tier = tier
        else:
            next_tier = tier
            break

    if next_tier:
        current_threshold = (
            reached_tier.min_total_points
            if reached_tier
            else 0
        )

        level_range = (
            next_tier.min_total_points
            - current_threshold
        )

        points_in_level = total_points - current_threshold

        percent = (
            min(
                100,
                max(
                    0,
                    points_in_level * 100 // level_range,
                ),
            )
            if level_range > 0
            else 0
        )

        return {
            'percent': percent,
            'total_points': total_points,
            'next_tier': next_tier.get_code_display(),
            'target_points': next_tier.min_total_points,
            'remaining_points': (
                next_tier.min_total_points - total_points
            ),
            'is_max': False,
        }

    if reached_tier:
        return {
            'percent': 100,
            'total_points': total_points,
            'is_max': True,
        }

    return None


# =========================================================
# MODULE 5 - HỒ SƠ CUSTOMER 360°
# TÍCH HỢP ORDER TỪ MODULE 4
# =========================================================

@role_required('CSKH', 'MANAGER')
def customer_detail(request, customer_id):

    # 1. Thông tin khách hàng
    customer = get_object_or_404(
        Customer,
        pk=customer_id,
    )

    # 2. Tài khoản Loyalty
    loyalty_account = (
        LoyaltyAccount.objects
        .select_related('tier')
        .filter(customer=customer)
        .first()
    )

    # 3. Lịch sử giao dịch điểm
    if loyalty_account:
        transactions = (
            loyalty_account.transactions
            .all()
            .order_by('-created_at', '-pk')
        )
    else:
        transactions = []

    # 4. Tiến độ nâng hạng
    loyalty_progress = get_loyalty_progress(
        loyalty_account
    )

    # 5. Lịch sử chăm sóc
    care_records = (
        CareRecord.objects
        .filter(customer=customer)
        .select_related('created_by')
        .order_by('-created_at', '-pk')
    )

    # 6. Ticket từ Module 3
    ticket_queryset = (
        Ticket.objects
        .filter(khach_hang=customer)
        .order_by('-thoi_diem_tao', '-pk')
    )

    ticket_count = ticket_queryset.count()
    tickets = ticket_queryset[:10]

    # 7. CSAT gần nhất
    latest_csat = (
        CSAT.objects
        .filter(ticket__khach_hang=customer)
        .select_related('ticket')
        .order_by('-created_at', '-pk')
        .first()
    )

    # 8. Lịch sử CSAT
    csat_history = (
        CSAT.objects
        .filter(ticket__khach_hang=customer)
        .select_related('ticket')
        .order_by('-created_at', '-pk')
    )

    # 9. DỮ LIỆU ĐƠN HÀNG TỪ MODULE 4
    # Chỉ đọc dữ liệu của khách hàng hiện tại.
    order_data = get_customer_order_360(customer)

    # 10. Context Customer 360°
    context = {
        'customer': customer,
        'loyalty_account': loyalty_account,
        'transactions': transactions,
        'care_records': care_records,
        'tickets': tickets,
        'ticket_count': ticket_count,
        'latest_csat': latest_csat,
        'csat_history': csat_history,
        'loyalty_progress': loyalty_progress,
    }

    # Bổ sung toàn bộ thống kê và lịch sử Order.
    context.update(order_data)

    return render(
        request,
        'customers/customer_detail.html',
        context,
    )


# =========================================================
# MODULE 5 - LƯU GHI CHÚ / HOẠT ĐỘNG CHĂM SÓC
# =========================================================

@role_required('CSKH', 'MANAGER')
@require_POST
def add_care_record(request, customer_id):

    customer = get_object_or_404(
        Customer,
        pk=customer_id,
    )

    care_type = request.POST.get(
        'care_type',
        CareRecord.CareType.NOTE,
    )

    content = (
        request.POST.get('content') or ''
    ).strip()

    if care_type not in CareRecord.CareType.values:
        messages.error(
            request,
            'Hình thức chăm sóc không hợp lệ.',
        )

    elif not content:
        messages.error(
            request,
            'Vui lòng nhập nội dung chăm sóc.',
        )

    elif len(content) > 500:
        messages.error(
            request,
            'Nội dung không được quá 500 ký tự.',
        )

    else:
        CareRecord.objects.create(
            customer=customer,
            created_by=request.user,
            care_type=care_type,
            content=content,
        )

        messages.success(
            request,
            'Đã lưu nội dung chăm sóc thành công.',
        )

    return redirect(
        'customers:detail',
        customer_id=customer.pk,
    )


# =========================================================
# MODULE 5 - CHĂM SÓC KHÁCH HÀNG CÓ CSAT THẤP
# =========================================================

@role_required('CSKH', 'MANAGER')
@require_http_methods(['GET', 'POST'])
def csat_care(request, customer_id):

    customer = get_object_or_404(
        Customer,
        pk=customer_id,
    )

    if request.method == 'POST':
        form = CareInteractionForm(request.POST)

        if form.is_valid():
            care_record = form.save(commit=False)
            care_record.customer = customer
            care_record.created_by = request.user
            care_record.save()

            messages.success(
                request,
                'Đã lưu hoạt động chăm sóc thành công.',
            )

            return redirect(
                'customers:csat_care',
                customer_id=customer.pk,
            )

    else:
        form = CareInteractionForm(
            initial={
                'care_type': CareRecord.CareType.CALL,
            }
        )

    care_records = (
        CareRecord.objects
        .filter(customer=customer)
        .select_related('created_by')
        .order_by('-created_at', '-pk')
    )

    latest_csat = (
        CSAT.objects
        .filter(ticket__khach_hang=customer)
        .select_related('ticket')
        .order_by('-created_at', '-pk')
        .first()
    )

    latest_ticket = (
        latest_csat.ticket
        if latest_csat is not None
        else None
    )

    is_low_csat = (
        latest_csat is not None
        and latest_csat.score <= 3
    )

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
        context,
    )


# =========================================================
# MODULE 5 - KHÁCH HÀNG GỬI ĐÁNH GIÁ CSAT
# =========================================================

@login_required
@require_http_methods(['GET', 'POST'])
def submit_csat(request, ticket_id):

    ticket = get_object_or_404(
        Ticket.objects.select_related(
            'khach_hang',
            'danh_muc',
            'nguoi_phu_trach',
        ),
        pk=ticket_id,
        khach_hang__ma_tai_khoan=request.user,
    )

    existing_csat = (
        CSAT.objects
        .filter(ticket=ticket)
        .first()
    )

    can_rate = (
        ticket.trang_thai in ['RESOLVED', 'CLOSED']
        and ticket.trang_thai_xac_nhan == 'AGREED'
    )

    form = CSATForm(request.POST or None)

    if (
        request.method == 'POST'
        and existing_csat is None
        and can_rate
        and form.is_valid()
    ):
        csat, created = CSAT.objects.get_or_create(
            ticket=ticket,
            defaults={
                'score': form.cleaned_data['score'],
                'comment': form.cleaned_data.get(
                    'comment',
                    '',
                ),
            },
        )

        if created:
            messages.success(
                request,
                'Cảm ơn bạn đã gửi đánh giá cho HULO!',
            )

        return redirect(
            'customers:submit_csat',
            ticket_id=ticket.pk,
        )

    context = {
        'ticket': ticket,
        'form': form,
        'existing_csat': existing_csat,
        'can_rate': can_rate,
        'rating_values': ['5', '4', '3', '2', '1'],
        'selected_score': request.POST.get('score', ''),
    }

    return render(
        request,
        'customers/csat_form.html',
        context,
    )


# =========================================================
# MODULE 5 - CHI TIẾT LOYALTY
# =========================================================

@role_required('CSKH', 'MANAGER')
def loyalty_detail(request, customer_id):

    customer = get_object_or_404(
        Customer,
        pk=customer_id,
    )

    loyalty_account = (
        LoyaltyAccount.objects
        .select_related('tier')
        .filter(customer=customer)
        .first()
    )

    if loyalty_account:
        transactions = (
            loyalty_account.transactions
            .all()
            .order_by('-created_at', '-pk')
        )
    else:
        transactions = []

    loyalty_progress = get_loyalty_progress(
        loyalty_account
    )

    return render(
        request,
        'customers/loyalty_detail.html',
        {
            'customer': customer,
            'loyalty_account': loyalty_account,
            'transactions': transactions,
            'loyalty_progress': loyalty_progress,
        },
    )


# =========================================================
# MODULE 5 - TỔNG QUAN LOYALTY
# =========================================================

@role_required('CSKH', 'MANAGER')
def loyalty_overview(request):

    keyword = request.GET.get('q', '').strip()

    all_accounts = LoyaltyAccount.objects.all()

    total_accounts = all_accounts.count()

    total_points_balance = (
        all_accounts.aggregate(
            total=Sum('points_balance')
        )['total']
        or 0
    )

    loyalty_accounts = (
        all_accounts
        .select_related('customer', 'tier')
        .order_by('customer__ma_khach_hang')
    )

    if keyword:
        conditions = (
            Q(customer__ho_ten__icontains=keyword)
            | Q(customer__email__icontains=keyword)
        )

        if keyword.isdecimal():
            conditions |= Q(
                customer__ma_khach_hang=int(keyword)
            )

        loyalty_accounts = loyalty_accounts.filter(
            conditions
        )

    return render(
        request,
        'customers/loyalty_overview.html',
        {
            'keyword': keyword,
            'loyalty_accounts': loyalty_accounts,
            'total_accounts': total_accounts,
            'total_points_balance': total_points_balance,
        },
    )


# =========================================================
# MODULE 5 - GIAO DỊCH LOYALTY / ĐỔI VOUCHER DEMO
# =========================================================

@role_required('CSKH', 'MANAGER')
@require_http_methods(['GET', 'POST'])
def loyalty_adjust_demo(request, customer_id):

    if not settings.DEBUG:
        raise PermissionDenied(
            'Chức năng giao dịch Loyalty DEMO không được bật.'
        )

    customer = get_object_or_404(
        Customer,
        pk=customer_id,
    )

    loyalty_account = get_object_or_404(
        LoyaltyAccount.objects.select_related('tier'),
        customer=customer,
    )

    preview = None

    if request.method == 'POST':
        form = LoyaltyVoucherTransactionForm(
            request.POST
        )
    else:
        form = LoyaltyVoucherTransactionForm(
            initial={
                'idempotency_key': uuid4(),
                'transaction_type': 'EARN',
            }
        )

    if request.method == 'POST' and form.is_valid():

        data = form.cleaned_data
        action = request.POST.get('action', '')
        transaction_type = data['transaction_type']

        try:
            # -----------------------------------------
            # CỘNG ĐIỂM LOYALTY
            # -----------------------------------------
            if transaction_type == 'EARN':

                if action != 'earn':
                    raise ValueError(
                        'Thao tác cộng điểm không hợp lệ.'
                    )

                change_loyalty_points(
                    customer=customer,
                    transaction_type='EARN',
                    points=data['points'],
                    description=(
                        'DEMO - ' + data['description']
                    ),
                    performed_by=request.user,
                    idempotency_key=data['idempotency_key'],
                )

                messages.success(
                    request,
                    'Đã xử lý yêu cầu cộng điểm Loyalty.',
                )

                return redirect(
                    'customers:loyalty_detail',
                    customer_id=customer.pk,
                )

            # -----------------------------------------
            # ĐỔI VOUCHER
            # -----------------------------------------
            reward = data['reward']

            if action == 'preview':

                loyalty_account.refresh_from_db()

                if (
                    loyalty_account.points_balance
                    < reward.points_cost
                ):
                    raise ValueError(
                        'Khách hàng không đủ điểm đổi Voucher này.'
                    )

                preview = {
                    'reward': reward,
                    'remaining_balance': (
                        loyalty_account.points_balance
                        - reward.points_cost
                    ),
                }

            elif action == 'confirm':

                try:
                    confirmed = signing.loads(
                        request.POST.get(
                            'preview_token',
                            '',
                        ),
                        salt='m5-loyalty-voucher-preview',
                        max_age=900,
                    )

                except signing.BadSignature:
                    raise ValueError(
                        'Thông tin xác nhận đã hết hạn '
                        'hoặc không hợp lệ. '
                        'Vui lòng xem trước lại.'
                    )

                expected = {
                    'customer_id': customer.pk,
                    'user_id': request.user.pk,
                    'key': str(data['idempotency_key']),
                    'reward_id': reward.pk,
                    'name': reward.name,
                    'cost': reward.points_cost,
                    'amount': reward.discount_amount,
                    'terms': reward.terms,
                    'days': reward.validity_days,
                    'description': data['description'],
                }

                if confirmed != expected:
                    raise ValueError(
                        'Thông tin giao dịch đã thay đổi. '
                        'Vui lòng xem trước lại.'
                    )

                voucher, created = redeem_loyalty_voucher(
                    customer=customer,
                    reward_id=reward.pk,
                    description=data['description'],
                    performed_by=request.user,
                    idempotency_key=data['idempotency_key'],
                )

                messages.success(
                    request,
                    (
                        'Đổi Voucher thành công.'
                        if created
                        else 'Yêu cầu này đã được xử lý trước đó.'
                    ),
                )

                return redirect(
                    request.path
                    + '?voucher='
                    + str(voucher.reference_code)
                )

            else:
                raise ValueError(
                    'Thao tác đổi Voucher không hợp lệ.'
                )

        except ValueError as error:
            form.add_error(None, str(error))

    # -----------------------------------------
    # TẠO TOKEN XÁC NHẬN VOUCHER
    # -----------------------------------------
    preview_token = ''

    if preview:
        reward = preview['reward']

        preview_token = signing.dumps(
            {
                'customer_id': customer.pk,
                'user_id': request.user.pk,
                'key': str(
                    form.cleaned_data['idempotency_key']
                ),
                'reward_id': reward.pk,
                'name': reward.name,
                'cost': reward.points_cost,
                'amount': reward.discount_amount,
                'terms': reward.terms,
                'days': reward.validity_days,
                'description': form.cleaned_data[
                    'description'
                ],
            },
            salt='m5-loyalty-voucher-preview',
        )

    # -----------------------------------------
    # LỊCH SỬ VOUCHER
    # -----------------------------------------
    vouchers = (
        LoyaltyRedemption.objects
        .filter(
            transaction__account__customer=customer
        )
        .order_by('-issued_at', '-pk')[:20]
    )

    loyalty_account.refresh_from_db()

    return render(
        request,
        'customers/loyalty_adjust_demo.html',
        {
            'customer': customer,
            'loyalty_account': loyalty_account,
            'form': form,
            'preview': preview,
            'preview_token': preview_token,
            'rewards': (
                LoyaltyReward.objects
                .filter(is_enabled=True)
                .order_by('points_cost', 'pk')
            ),
            'vouchers': vouchers,
        },
    )
