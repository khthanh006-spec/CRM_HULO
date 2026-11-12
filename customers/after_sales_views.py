
from uuid import UUID

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from accounts.permissions import role_required
from tickets.models import TicketLog

from .models import (
    AfterSalesBenefit,
    AfterSalesDelivery,
    AfterSalesProgram,
    CareRecord,
    CSAT,
    Customer,
    LoyaltyAccount,
    RetentionCase,
)


class VoucherIssueForm(forms.Form):
    customer = forms.ModelChoiceField(
        label='Khách hàng nhận Voucher',
        queryset=Customer.objects.none(),
        empty_label='-- Chọn khách hàng --',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['customer'].queryset = (
            Customer.objects
            .all()
            .order_by('ho_ten', 'pk')
        )


def voucher_issue_error(benefit, customer):
    """Kiểm tra hiệu lực và điều kiện hạng Loyalty."""
    now = timezone.now()
    program = benefit.program

    if not program.is_enabled:
        return 'Chương trình đang tạm dừng.'

    if now < program.starts_at:
        return 'Chương trình chưa đến thời gian triển khai.'

    if now > program.ends_at:
        return 'Chương trình đã hết hiệu lực.'

    if benefit.benefit_type != AfterSalesBenefit.BenefitType.VOUCHER:
        return 'Quyền lợi được chọn không phải Voucher.'

    if not benefit.is_enabled:
        return 'Voucher đang tạm dừng cấp.'

    if not benefit.valid_from <= now <= benefit.valid_until:
        return 'Voucher chưa có hiệu lực hoặc đã hết hạn.'

    eligible_tier_ids = list(
        program.eligible_tiers.values_list('pk', flat=True)
    )

    if eligible_tier_ids:
        account = (
            LoyaltyAccount.objects
            .filter(customer=customer)
            .first()
        )

        if account is None:
            return (
                'Khách hàng chưa có tài khoản Loyalty '
                'để nhận Voucher của chương trình này.'
            )

        if account.tier_id not in eligible_tier_ids:
            return (
                'Hạng Loyalty của khách hàng không thuộc '
                'các hạng được áp dụng.'
            )

    return ''


# ==================================================
# CẤP VOUCHER - CHỈ CSKH
# ==================================================

@role_required('CSKH')
@require_http_methods(['GET', 'POST'])
def issue_voucher(request, benefit_id):
    benefit = get_object_or_404(
        AfterSalesBenefit.objects.select_related('program'),
        pk=benefit_id,
        benefit_type=AfterSalesBenefit.BenefitType.VOUCHER,
    )

    retention_case = None
    case_id = request.GET.get('case', '')

    if case_id:
        if not case_id.isdecimal():
            raise PermissionDenied('Mã ca không hợp lệ.')

        retention_case = get_object_or_404(
            RetentionCase,
            pk=int(case_id),
        )

        if not can_work_case(request.user, retention_case):
            raise PermissionDenied(
                'Bạn không được xử lý ca này.'
            )

        if retention_case.status != RetentionCase.Status.IN_PROGRESS:
            messages.error(
                request,
                'Cần tiếp nhận ca trước khi cấp Voucher.',
            )
            return redirect(
                'customers:retention_detail',
                case_id=retention_case.pk,
            )

        if not benefit.is_apology:
            raise PermissionDenied(
                'Ca giữ chân chỉ chọn Voucher được phân loại đền bù.'
            )

    elif benefit.is_apology:
        messages.error(
            request,
            'Hãy mở ca giữ chân để cấp Voucher đền bù.',
        )
        return redirect('customers:after_sales_overview')

    form = VoucherIssueForm(
        request.POST if request.method == 'POST' else None
    )

    if retention_case:
        form.fields['customer'].queryset = Customer.objects.filter(
            pk=retention_case.customer_id
        )
        form.fields['customer'].initial = retention_case.customer_id

    preview = False
    customer = None

    if request.method == 'POST' and form.is_valid():
        customer = form.cleaned_data['customer']

        error = voucher_issue_error(benefit, customer)

        already_issued = AfterSalesDelivery.objects.filter(
            benefit=benefit,
            customer=customer,
            issued_at__isnull=False,
        ).exists()

        if error:
            form.add_error(None, error)

        elif already_issued:
            form.add_error(
                None,
                'Khách hàng đã được cấp Voucher này. '
                'Hệ thống không cấp trùng.',
            )

        elif request.POST.get('action') == 'confirm':
            try:
                with transaction.atomic():
                    if retention_case:
                        retention_case = (
                            RetentionCase.objects
                            .select_for_update()
                            .get(pk=retention_case.pk)
                        )

                        if (
                            not can_work_case(request.user, retention_case)
                            or retention_case.status
                            != RetentionCase.Status.IN_PROGRESS
                            or retention_case.customer_id != customer.pk
                        ):
                            raise ValueError(
                                'Ca không còn đủ điều kiện cấp Voucher.'
                            )

                    # Khóa chương trình và Voucher trong lúc cấp.
                    program = (
                        AfterSalesProgram.objects
                        .select_for_update()
                        .get(pk=benefit.program_id)
                    )

                    benefit = (
                        AfterSalesBenefit.objects
                        .select_for_update()
                        .get(pk=benefit.pk)
                    )
                    benefit.program = program

                    # Khóa khách hàng và tài khoản Loyalty hiện có.
                    customer = (
                        Customer.objects
                        .select_for_update()
                        .get(pk=customer.pk)
                    )

                    list(
                        LoyaltyAccount.objects
                        .select_for_update()
                        .filter(customer=customer)
                    )

                    # Kiểm tra lại ngay trước khi ghi dữ liệu.
                    error = voucher_issue_error(
                        benefit,
                        customer,
                    )

                    if error:
                        raise ValueError(error)

                    if bool(benefit.is_apology) != bool(retention_case):
                        raise ValueError(
                            'Phân loại Voucher đã thay đổi; hãy chọn lại.'
                        )

                    delivery, created = (
                        AfterSalesDelivery.objects
                        .get_or_create(
                            benefit=benefit,
                            customer=customer,
                            defaults={
                                'performed_by': request.user,
                                'channel': (
                                    AfterSalesDelivery
                                    .Channel.INTERNAL
                                ),
                            },
                        )
                    )

                    if (
                        delivery.issued_at is not None
                        or delivery.status in [
                            AfterSalesDelivery.Status.ISSUED,
                            AfterSalesDelivery.Status.SENT,
                        ]
                    ):
                        raise ValueError(
                            'Khách hàng đã nhận Voucher này. '
                            'Hệ thống không cấp trùng.'
                        )

                    content = (
                        f'Chương trình: {program.name}\n'
                        f'Voucher: {benefit.name}\n'
                        f'Mã: {delivery.reference_code}\n'
                        f'Nội dung: {benefit.description}\n'
                        f'Điều kiện: {benefit.terms}\n'
                        f'Hạn sử dụng: '
                        f'{timezone.localtime(benefit.valid_until):%d/%m/%Y %H:%M}'
                    )

                    care_content = (
                        f'Đã cấp Voucher. '
                        f'CT: {program.code}. '
                        f'Voucher: {benefit.name}. '
                        f'Mã: {delivery.reference_code}. '
                        f'Ghi nhận trên CRM.'
                    )

                    if delivery.care_record_id is None:
                        delivery.care_record = (
                            CareRecord.objects.create(
                                customer=customer,
                                created_by=request.user,
                                care_type=(
                                    CareRecord.CareType.OTHER
                                ),
                                content=care_content,
                                retention_case=retention_case,
                            )
                        )

                    delivery.retention_case = retention_case
                    delivery.is_apology = benefit.is_apology
                    delivery.performed_by = request.user
                    delivery.channel = (
                        AfterSalesDelivery.Channel.INTERNAL
                    )
                    delivery.status = (
                        AfterSalesDelivery.Status.ISSUED
                    )
                    delivery.message_content = content
                    delivery.error_message = ''
                    delivery.issued_at = timezone.now()
                    delivery.attempt_count += 1

                    delivery.full_clean()
                    delivery.save()

            except (ValueError, ValidationError) as error:
                form.add_error(None, str(error))

            except DatabaseError:
                form.add_error(
                    None,
                    'Chưa thể lưu. Vui lòng kiểm tra lịch sử rồi thử lại.',
                )

            else:
                messages.success(
                    request,
                    f'Đã cấp Voucher cho {customer.ho_ten}. '
                    'Lịch sử Customer 360° đã được cập nhật.',
                )

                if retention_case:
                    return redirect(
                        'customers:retention_detail',
                        case_id=retention_case.pk,
                    )

                return redirect(
                    'customers:issue_voucher',
                    benefit_id=benefit.pk,
                )

        else:
            preview = True

    recent_deliveries = (
        AfterSalesDelivery.objects
        .filter(
            benefit=benefit,
            issued_at__isnull=False,
        )
        .select_related('customer', 'performed_by')
        .order_by('-issued_at', '-pk')[:20]
    )

    return render(
        request,
        'customers/issue_voucher.html',
        {
            'benefit': benefit,
            'retention_case': retention_case,
            'form': form,
            'preview': preview,
            'selected_customer': customer,
            'recent_deliveries': recent_deliveries,
        },
    )


# ==================================================
# VOUCHER CỦA KHÁCH HÀNG
# ==================================================

@login_required
@require_http_methods(['GET'])
def my_vouchers(request):
    customer = get_object_or_404(
        Customer,
        ma_tai_khoan=request.user,
    )

    vouchers = (
        AfterSalesDelivery.objects
        .filter(
            customer=customer,
            issued_at__isnull=False,
        )
        .select_related(
            'benefit',
            'benefit__program',
        )
        .order_by('-issued_at', '-pk')
    )

    now = timezone.now()
    voucher_rows = []

    for delivery in vouchers:
        benefit = delivery.benefit

        # Hạn sử dụng của Voucher đã cấp được xét riêng
        # với thời gian triển khai cấp của chương trình.
        if not benefit.is_enabled:
            availability = 'Tạm dừng'
            badge_class = 'paused'

        elif now < benefit.valid_from:
            availability = 'Chưa đến ngày sử dụng'
            badge_class = 'upcoming'

        elif now > benefit.valid_until:
            availability = 'Đã hết hạn'
            badge_class = 'expired'

        else:
            availability = 'Trong thời hạn sử dụng'
            badge_class = 'active'

        voucher_rows.append({
            'delivery': delivery,
            'availability': availability,
            'badge_class': badge_class,
        })

    return render(
        request,
        'customers/my_vouchers.html',
        {
            'customer': customer,
            'voucher_rows': voucher_rows,
        },
    )


# ==================================================
# LỊCH SỬ VOUCHER
# ==================================================

@role_required('CSKH', 'MANAGER')
@require_http_methods(['GET'])
def voucher_history(request):
    keyword = request.GET.get('q', '').strip()

    deliveries = (
        AfterSalesDelivery.objects
        .filter(issued_at__isnull=False)
        .select_related(
            'customer',
            'benefit',
            'benefit__program',
            'performed_by',
        )
        .order_by('-issued_at', '-pk')
    )

    if keyword:
        conditions = (
            Q(customer__ho_ten__icontains=keyword)
            | Q(customer__email__icontains=keyword)
            | Q(benefit__name__icontains=keyword)
            | Q(benefit__program__code__icontains=keyword)
            | Q(benefit__program__name__icontains=keyword)
        )

        # Tìm chính xác mã Voucher nếu nhập UUID hợp lệ.
        try:
            reference = UUID(keyword)
        except ValueError:
            pass
        else:
            conditions |= Q(reference_code=reference)

        deliveries = deliveries.filter(conditions)

    paginator = Paginator(deliveries, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'customers/voucher_history.html',
        {
            'keyword': keyword,
            'page_obj': page_obj,
            'total_results': paginator.count,
        },
    )


# ==================================================
# CA GIỮ CHÂN - PHÂN QUYỀN
# ==================================================

def is_manager(user):
    profile = getattr(user, 'staff_profile', None)

    return bool(
        user.is_superuser
        or (profile and profile.vai_tro == 'MANAGER')
    )


def ticket_cskh_user_id(ticket):
    """
    Lấy ID tài khoản CSKH phụ trách Ticket gốc.

    Retention Case kế thừa CSKH từ Module 3.
    """
    if not ticket or not ticket.nguoi_phu_trach_id:
        return None

    staff = ticket.nguoi_phu_trach

    if staff.vai_tro != 'CSKH':
        return None

    return staff.ma_tai_khoan_id


def can_work_case(user, case):
    """
    Chỉ CSKH gốc được xử lý Retention Case.

    MANAGER chỉ có quyền theo dõi.
    """
    if not user.is_authenticated or is_manager(user):
        return False

    profile = getattr(user, 'staff_profile', None)

    return bool(
        profile
        and profile.vai_tro == 'CSKH'
        and case.assigned_to_id == user.pk
        and ticket_cskh_user_id(case.ticket) == user.pk
    )


def can_claim_case(user, case):
    """
    Chỉ CSKH gốc được tiếp nhận ca PENDING.

    Ca có thể đã được phân công nhưng chưa tiếp nhận.
    """
    if not user.is_authenticated or is_manager(user):
        return False

    profile = getattr(user, 'staff_profile', None)

    return bool(
        profile
        and profile.vai_tro == 'CSKH'
        and case.status == RetentionCase.Status.PENDING
        and ticket_cskh_user_id(case.ticket) == user.pk
        and case.assigned_to_id in (None, user.pk)
    )


def page_context(request, queryset):
    page = Paginator(
        queryset,
        20,
    ).get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)

    return {
        'case_page': page,
        'filter_query': params.urlencode(),
    }


# ==================================================
# TỔNG QUAN CHĂM SÓC SAU BÁN
# ==================================================

@role_required('CSKH', 'MANAGER')
@require_http_methods(['GET'])
def after_sales_overview(request):
    now = timezone.now()

    keyword = request.GET.get('q', '').strip()
    active_tab = request.GET.get('tab', 'retention')

    if active_tab not in ['retention', 'campaigns', 'history']:
        active_tab = 'retention'

    cases = RetentionCase.objects.select_related(
        'customer',
        'ticket',
        'assigned_to',
        'source_csat',
    ).order_by('-triggered_at', '-pk')

    counts = RetentionCase.objects.aggregate(
        urgent_count=Count(
            'pk',
            filter=Q(
                status='PENDING',
                risk_level='HIGH',
            ),
        ),
        progress_count=Count(
            'pk',
            filter=Q(status='IN_PROGRESS'),
        ),
        saved_count=Count(
            'pk',
            filter=Q(status='SAVED'),
        ),
    )

    apology_count = AfterSalesDelivery.objects.filter(
        is_apology=True,
        issued_at__isnull=False,
    ).count()

    case_status = request.GET.get('case_status', '')
    risk = request.GET.get('risk', '')
    owner = request.GET.get('owner', '')

    if case_status in dict(RetentionCase.Status.choices):
        cases = cases.filter(status=case_status)
    else:
        case_status = ''

    if risk in dict(RetentionCase.RiskLevel.choices):
        cases = cases.filter(risk_level=risk)
    else:
        risk = ''

    if owner == 'mine':
        cases = cases.filter(assigned_to=request.user)

    elif owner == 'unassigned':
        cases = cases.filter(assigned_to__isnull=True)

    else:
        owner = ''

    programs = (
        AfterSalesProgram.objects
        .prefetch_related(
            'eligible_tiers',
            'benefits',
        )
    )

    selected_type = request.GET.get('type', '')
    selected_status = request.GET.get('status', '')

    if selected_type in dict(AfterSalesProgram.ProgramType.choices):
        programs = programs.filter(
            program_type=selected_type
        )
    else:
        selected_type = ''

    status_choices = [
        ('ACTIVE', 'Đang hiệu lực'),
        ('UPCOMING', 'Sắp diễn ra'),
        ('EXPIRED', 'Hết hạn'),
        ('PAUSED', 'Tạm dừng'),
    ]

    if selected_status == 'ACTIVE':
        programs = programs.filter(
            is_enabled=True,
            starts_at__lte=now,
            ends_at__gte=now,
        )

    elif selected_status == 'UPCOMING':
        programs = programs.filter(
            is_enabled=True,
            starts_at__gt=now,
        )

    elif selected_status == 'EXPIRED':
        programs = programs.filter(
            is_enabled=True,
            ends_at__lt=now,
        )

    elif selected_status == 'PAUSED':
        programs = programs.filter(
            is_enabled=False,
        )

    else:
        selected_status = ''

    if keyword:
        if active_tab == 'campaigns':
            programs = programs.filter(
                Q(code__icontains=keyword)
                | Q(name__icontains=keyword)
            )

        else:
            condition = (
                Q(customer__ho_ten__icontains=keyword)
                | Q(customer__email__icontains=keyword)
                | Q(ticket__ma_ticket__icontains=keyword)
            )

            code = keyword.upper().removeprefix('RC')

            if code.isdecimal():
                condition |= Q(pk=int(code))

            cases = cases.filter(condition)

    context = {
        'active_tab': active_tab,
        'keyword': keyword,
        'programs': programs,
        'selected_type': selected_type,
        'selected_status': selected_status,
        'status_choices': status_choices,
        'type_choices': AfterSalesProgram.ProgramType.choices,
        'case_status': case_status,
        'risk': risk,
        'owner': owner,
        'case_status_choices': RetentionCase.Status.choices,
        'risk_choices': RetentionCase.RiskLevel.choices,
        'apology_count': apology_count,
        **counts,
        **page_context(request, cases),
    }

    # Lịch sử cấp Voucher hiển thị tại trang tổng quan.
    history_keyword = request.GET.get(
        'history_q',
        '',
    ).strip()

    voucher_history = (
        AfterSalesDelivery.objects
        .filter(
            issued_at__isnull=False,
            benefit__benefit_type='VOUCHER',
        )
        .select_related(
            'customer',
            'benefit',
            'benefit__program',
            'performed_by',
        )
        .order_by('-issued_at', '-pk')
    )

    if history_keyword:
        conditions = (
            Q(customer__ho_ten__icontains=history_keyword)
            | Q(customer__email__icontains=history_keyword)
            | Q(benefit__name__icontains=history_keyword)
            | Q(benefit__program__code__icontains=history_keyword)
            | Q(benefit__program__name__icontains=history_keyword)
        )

        try:
            reference = UUID(history_keyword)
        except ValueError:
            pass
        else:
            conditions |= Q(reference_code=reference)

        voucher_history = voucher_history.filter(conditions)

    history_paginator = Paginator(
        voucher_history,
        20,
    )

    history_page = history_paginator.get_page(
        request.GET.get('history_page')
    )

    # Giữ các bộ lọc khi chuyển trang lịch sử.
    history_params = request.GET.copy()
    history_params.pop('history_page', None)

    # Link xóa tìm kiếm lịch sử giữ bộ lọc chương trình.
    history_clear_params = history_params.copy()
    history_clear_params.pop('history_q', None)

    # Giữ các bộ lọc khác khi tìm trong lịch sử.
    history_preserved_filters = [
        (key, value)
        for key, values in request.GET.lists()
        if key not in ('history_q', 'history_page')
        for value in values
    ]

    context.update({
        'history_keyword': history_keyword,
        'history_page': history_page,
        'history_total': history_paginator.count,
        'history_query': history_params.urlencode(),
        'history_clear_query': history_clear_params.urlencode(),
        'history_preserved_filters': history_preserved_filters,
    })

    return render(
        request,
        'customers/after_sales_overview.html',
        context,
    )


# ==================================================
# ĐỒNG BỘ RETENTION CASE TỪ CSAT VÀ REOPENED
# ==================================================

@role_required('CSKH', 'MANAGER')
@require_POST
def sync_retention_cases(request):
    created_count = 0
    assigned_count = 0

    try:
        with transaction.atomic():

            # Tạo ca từ đánh giá CSAT thấp.
            csats = (
                CSAT.objects
                .filter(score__in=[1, 2])
                .select_related(
                    'ticket__nguoi_phu_trach',
                )
            )

            for csat in csats:
                owner_id = ticket_cskh_user_id(
                    csat.ticket
                )

                case, created = RetentionCase.objects.get_or_create(
                    source_csat=csat,
                    defaults={
                        'customer_id': csat.ticket.khach_hang_id,
                        'ticket_id': csat.ticket_id,
                        'source': 'LOW_CSAT',
                        'assigned_to_id': owner_id,
                        'triggered_at': csat.created_at,
                        'trigger_summary': (
                            f'CSAT {csat.score}/5. {csat.comment}'
                        )[:1000],
                    },
                )

                created_count += int(created)

                # Bổ sung CSKH cho ca PENDING cũ chưa phân công.
                if (
                    not created
                    and case.status == RetentionCase.Status.PENDING
                    and case.assigned_to_id is None
                    and owner_id is not None
                ):
                    case.assigned_to_id = owner_id
                    case.full_clean()
                    case.save(
                        update_fields=[
                            'assigned_to',
                            'updated_at',
                        ]
                    )
                    assigned_count += 1

            # Tạo ca từ sự kiện mở lại Ticket.
            logs = (
                TicketLog.objects
                .filter(
                    hanh_dong='KHÁCH HÀNG YÊU CẦU MỞ LẠI'
                )
                .select_related(
                    'ticket__nguoi_phu_trach',
                )
            )

            for log in logs:
                owner_id = ticket_cskh_user_id(
                    log.ticket
                )

                case, created = RetentionCase.objects.get_or_create(
                    source_ticket_log=log,
                    defaults={
                        'customer_id': log.ticket.khach_hang_id,
                        'ticket_id': log.ticket_id,
                        'source': 'REOPENED',
                        'assigned_to_id': owner_id,
                        'triggered_at': log.thoi_diem,
                        'trigger_summary': log.noi_dung[:1000],
                    },
                )

                created_count += int(created)

                if (
                    not created
                    and case.status == RetentionCase.Status.PENDING
                    and case.assigned_to_id is None
                    and owner_id is not None
                ):
                    case.assigned_to_id = owner_id
                    case.full_clean()
                    case.save(
                        update_fields=[
                            'assigned_to',
                            'updated_at',
                        ]
                    )
                    assigned_count += 1

    except (DatabaseError, ValidationError):
        messages.error(
            request,
            'Chưa đồng bộ được; dữ liệu lần này đã hoàn tác. '
            'Hãy thử lại.',
        )

    else:
        messages.success(
            request,
            f'Đồng bộ xong: thêm {created_count} ca mới, '
            f'phân công {assigned_count} ca đang chờ.',
        )

    return redirect(
        'customers:after_sales_overview'
    )


# ==================================================
# BIỂU MẪU CHĂM SÓC RETENTION
# ==================================================

class RetentionCareForm(forms.Form):
    care_type = forms.ChoiceField(
        label='Hình thức chăm sóc',
        choices=CareRecord.CareType.choices,
    )

    content = forms.CharField(
        label='Nội dung hoạt động',
        max_length=500,
        widget=forms.Textarea,
    )


class RetentionCloseForm(forms.Form):
    outcome = forms.ChoiceField(
        label='Kết quả',
        choices=[
            (
                'SAVED',
                'Khách hàng xác nhận hài lòng lại',
            ),
            (
                'UNSUCCESSFUL',
                'Chưa giữ chân được',
            ),
        ],
    )

    resolution_note = forms.CharField(
        label='Kết quả xử lý',
        max_length=2000,
        widget=forms.Textarea,
    )

    customer_feedback = forms.CharField(
        label='Phản hồi khách hàng',
        max_length=2000,
        required=False,
        widget=forms.Textarea,
    )

    confirmed = forms.BooleanField(
        label='Tôi đã nhận được xác nhận hài lòng của khách hàng',
        required=False,
    )

    def clean(self):
        data = super().clean()

        if data.get('outcome') == 'SAVED':
            if not data.get('customer_feedback'):
                self.add_error(
                    'customer_feedback',
                    'Cần ghi lại phản hồi khách hàng.',
                )

            if not data.get('confirmed'):
                self.add_error(
                    'confirmed',
                    'Chỉ đánh dấu thành công khi có xác nhận thực tế.',
                )

        return data


# ==================================================
# CHI TIẾT VÀ XỬ LÝ RETENTION CASE
# ==================================================

@role_required('CSKH', 'MANAGER')
@require_http_methods(['GET', 'POST'])
def retention_detail(request, case_id):
    case = get_object_or_404(
        RetentionCase.objects.select_related(
            'customer',
            'ticket',
            'assigned_to',
            'source_csat',
        ),
        pk=case_id,
    )

    care_form = RetentionCareForm(
        prefix='care'
    )
    close_form = RetentionCloseForm(
        prefix='close'
    )

    if request.method == 'POST':

        # Quản lý chỉ được xem ca, không trực tiếp xử lý.
        if is_manager(request.user):
            raise PermissionDenied(
                'Quản lý chỉ được theo dõi ca giữ chân.'
            )

        action = request.POST.get('action')

        if action == 'care':
            care_form = RetentionCareForm(
                request.POST,
                prefix='care',
            )
            valid = care_form.is_valid()

        elif action == 'close':
            close_form = RetentionCloseForm(
                request.POST,
                prefix='close',
            )
            valid = close_form.is_valid()

        else:
            valid = action == 'claim'

        if not valid and action not in ['care', 'close']:
            messages.error(
                request,
                'Thao tác không hợp lệ.',
            )

        if valid:
            try:
                with transaction.atomic():
                    case = (
                        RetentionCase.objects
                        .select_for_update()
                        .get(pk=case_id)
                    )

                    if action == 'claim':

                        if not can_claim_case(request.user, case):
                            raise PermissionDenied(
                                'Chỉ CSKH phụ trách Ticket gốc '
                                'được tiếp nhận ca.'
                            )

                        case.assigned_to = request.user
                        case.status = RetentionCase.Status.IN_PROGRESS
                        case.started_at = timezone.now()

                        case.full_clean()
                        case.save()

                        CareRecord.objects.create(
                            customer_id=case.customer_id,
                            retention_case=case,
                            created_by=request.user,
                            care_type='NOTE',
                            content=(
                                f'Tiếp nhận ca giữ chân '
                                f'{case.case_code}.'
                            ),
                        )

                    else:
                        if not can_work_case(request.user, case):
                            raise PermissionDenied(
                                'Chỉ CSKH phụ trách Ticket gốc '
                                'được cập nhật ca.'
                            )

                        if case.status != RetentionCase.Status.IN_PROGRESS:
                            raise ValueError(
                                'Ca phải đang chăm sóc để cập nhật.'
                            )

                        if action == 'care':
                            CareRecord.objects.create(
                                customer_id=case.customer_id,
                                retention_case=case,
                                created_by=request.user,
                                **care_form.cleaned_data,
                            )

                        else:
                            data = close_form.cleaned_data

                            case.status = data['outcome']
                            case.resolution_note = data['resolution_note']
                            case.customer_feedback = data['customer_feedback']
                            case.closed_at = timezone.now()

                            case.satisfaction_confirmed_at = (
                                case.closed_at
                                if case.status == RetentionCase.Status.SAVED
                                else None
                            )

                            case.full_clean()
                            case.save()

                            # Nội dung đầy đủ nằm trên ca;
                            # CareRecord lưu tham chiếu ngắn.
                            CareRecord.objects.create(
                                customer_id=case.customer_id,
                                retention_case=case,
                                created_by=request.user,
                                care_type='NOTE',
                                content=(
                                    f'Kết thúc {case.case_code}: '
                                    f'{case.get_status_display()}. '
                                    f'{case.resolution_note}'
                                )[:500],
                            )

            except (ValueError, ValidationError) as error:
                messages.error(
                    request,
                    str(error),
                )

            except DatabaseError:
                messages.error(
                    request,
                    'Chưa lưu được. Dữ liệu lần này đã hoàn tác; '
                    'hãy thử lại.',
                )

            else:
                messages.success(
                    request,
                    'Đã cập nhật ca và lịch sử Customer 360°.',
                )
                return redirect(
                    'customers:retention_detail',
                    case_id=case.pk,
                )

            case.refresh_from_db()

    # Voucher phù hợp chỉ hiện với CSKH phụ trách.
    eligible = []

    if (
        case.status == RetentionCase.Status.IN_PROGRESS
        and can_work_case(request.user, case)
    ):
        already = AfterSalesDelivery.objects.filter(
            customer_id=case.customer_id,
            issued_at__isnull=False,
        ).values_list(
            'benefit_id',
            flat=True,
        )

        benefits = (
            AfterSalesBenefit.objects
            .filter(
                is_apology=True,
                benefit_type='VOUCHER',
            )
            .exclude(pk__in=already)
            .select_related('program')
        )

        for benefit in benefits:
            error = voucher_issue_error(
                benefit,
                case.customer,
            )

            print(
                f"[KIỂM TRA VOUCHER] "
                f"ID={benefit.pk} | "
                f"Tên={benefit.name} | "
                f"Kết quả={error or 'Đủ điều kiện'}"
            )

            if not error:
                eligible.append(benefit)

    return render(
        request,
        'customers/retention_detail.html',
        {
            'case': case,
            'care_form': care_form,
            'close_form': close_form,
            'can_work': can_work_case(
                request.user,
                case,
            ),
            'can_claim': can_claim_case(
                request.user,
                case,
            ),
            'eligible_benefits': eligible,
            'care_records': (
                case.care_records
                .select_related('created_by')
                .order_by('-created_at', '-pk')
            ),
            'case_deliveries': (
                case.voucher_deliveries
                .filter(issued_at__isnull=False)
                .select_related('benefit')
            ),
        },
    )


# ==================================================
# CHỌN VOUCHER CHĂM SÓC CSAT
# ==================================================

@role_required('CSKH', 'MANAGER')
@require_http_methods(['GET'])
def choose_csat_voucher(request, customer_id):
    customer = get_object_or_404(
        Customer,
        pk=customer_id,
    )

    benefits = (
        AfterSalesBenefit.objects
        .filter(
            benefit_type=(
                AfterSalesBenefit.BenefitType.VOUCHER
            ),
        )
        .select_related('program')
        .order_by('-is_apology', 'name', 'pk')
    )

    already_issued = set(
        AfterSalesDelivery.objects
        .filter(
            customer=customer,
            issued_at__isnull=False,
        )
        .values_list(
            'benefit_id',
            flat=True,
        )
    )

    available_rows = []
    unavailable_rows = []

    for benefit in benefits:
        reason = voucher_issue_error(
            benefit,
            customer,
        )

        if benefit.pk in already_issued:
            reason = 'Khách hàng đã nhận Voucher này.'

        row = {
            'benefit': benefit,
            'reason': reason,
        }

        if reason:
            unavailable_rows.append(row)
        else:
            available_rows.append(row)

    return render(
        request,
        'customers/choose_csat_voucher.html',
        {
            'customer': customer,
            'available_rows': available_rows,
            'unavailable_rows': unavailable_rows,
        },
    )
