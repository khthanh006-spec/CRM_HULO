
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import role_required

from .models import Customer, LoyaltyTier


# =========================================================
# MODULE 5 - DANH SÁCH KHÁCH HÀNG
# BỘ LỌC NÂNG CAO
# =========================================================

@role_required('CSKH', 'MANAGER')
def customer_list(request):

    # -----------------------------------------
    # 1. ĐỌC THAM SỐ BỘ LỌC
    # -----------------------------------------

    keyword = request.GET.get('q', '').strip()

    tier_id = request.GET.get(
        'tier',
        '',
    ).strip()

    date_range = request.GET.get(
        'date_range',
        '',
    ).strip()

    sort_by = request.GET.get(
        'sort',
        'newest',
    ).strip()

    # -----------------------------------------
    # 2. KIỂM TRA THAM SỐ HỢP LỆ
    # -----------------------------------------

    allowed_date_ranges = (
        '',
        '7',
        '30',
        '90',
    )

    if date_range not in allowed_date_ranges:
        date_range = ''

    sort_options = {
        'newest': (
            '-thoi_diem_tao',
            '-ma_khach_hang',
        ),
        'oldest': (
            'thoi_diem_tao',
            'ma_khach_hang',
        ),
        'name_asc': (
            'ho_ten',
            'ma_khach_hang',
        ),
        'name_desc': (
            '-ho_ten',
            '-ma_khach_hang',
        ),
        'code_asc': (
            'ma_khach_hang',
        ),
        'code_desc': (
            '-ma_khach_hang',
        ),
    }

    if sort_by not in sort_options:
        sort_by = 'newest'

    # -----------------------------------------
    # 3. DANH SÁCH HẠNG LOYALTY
    # -----------------------------------------

    tiers = list(
        LoyaltyTier.objects.order_by(
            'min_total_points',
            'pk',
        )
    )

    valid_tier_ids = {
        str(tier.pk)
        for tier in tiers
    }

    if (
        tier_id
        and tier_id != 'none'
        and tier_id not in valid_tier_ids
    ):
        tier_id = ''

    # -----------------------------------------
    # 4. QUERYSET KHÁCH HÀNG
    # -----------------------------------------

    customers = (
        Customer.objects
        .select_related(
            'loyalty_account',
            'loyalty_account__tier',
        )
        .all()
    )

    # -----------------------------------------
    # 5. TÌM KIẾM TỔNG HỢP
    # -----------------------------------------

    if keyword:

        conditions = (
            Q(ho_ten__icontains=keyword)
            | Q(email__icontains=keyword)
            | Q(so_dien_thoai__icontains=keyword)
        )

        if keyword.isdecimal():
            conditions |= Q(
                ma_khach_hang=int(keyword)
            )

        customers = customers.filter(
            conditions
        )

    # -----------------------------------------
    # 6. LỌC THEO HẠNG LOYALTY
    # -----------------------------------------

    if tier_id == 'none':

        customers = customers.filter(
            Q(loyalty_account__isnull=True)
            | Q(loyalty_account__tier__isnull=True)
        )

    elif tier_id:

        customers = customers.filter(
            loyalty_account__tier_id=int(tier_id)
        )

    # -----------------------------------------
    # 7. LỌC THEO THỜI GIAN TẠO
    # -----------------------------------------

    if date_range:

        days = int(date_range)

        start_date = (
            timezone.now()
            - timedelta(days=days)
        )

        customers = customers.filter(
            thoi_diem_tao__gte=start_date
        )

    # -----------------------------------------
    # 8. SẮP XẾP KẾT QUẢ
    # -----------------------------------------

    customers = customers.order_by(
        *sort_options[sort_by]
    )

    # -----------------------------------------
    # 9. PHÂN TRANG
    # -----------------------------------------

    paginator = Paginator(
        customers,
        10,
    )

    page_number = request.GET.get(
        'page',
        1,
    )

    page_obj = paginator.get_page(
        page_number
    )

    # Giữ nguyên bộ lọc khi chuyển trang.
    query_params = request.GET.copy()

    if 'page' in query_params:
        del query_params['page']

    filter_query = query_params.urlencode()

    # -----------------------------------------
    # 10. DỮ LIỆU TRẢ RA TEMPLATE
    # -----------------------------------------

    context = {
        'customers': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_results': paginator.count,
        'keyword': keyword,
        'tier_id': tier_id,
        'date_range': date_range,
        'sort_by': sort_by,
        'tiers': tiers,
        'filter_query': filter_query,
        'has_filters': bool(
            keyword
            or tier_id
            or date_range
            or sort_by != 'newest'
        ),
    }

    return render(
        request,
        'customers/customer_list.html',
        context,
    )
