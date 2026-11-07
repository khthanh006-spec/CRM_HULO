
# =========================================================
# CRM HULO - MODULE 5
# TONG QUAN CSAT & CHAM SOC KHACH HANG
# BO LOC NANG CAO
# =========================================================

from datetime import timedelta

from django.core.paginator import Paginator

from django.db.models import (
    Q,
    Avg,
    Count,
    OuterRef,
    Subquery,
)

from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import role_required

from .models import Customer, CSAT


@role_required('CSKH', 'MANAGER')
def csat_overview(request):
    """
    Trang tong quan CSAT va cham soc khach hang.

    Chuc nang:
    - Tim khach hang theo ma, ten, email, so dien thoai.
    - Hien thi danh gia CSAT gan nhat cua moi khach hang.
    - Loc theo so sao cua danh gia gan nhat.
    - Loc theo thoi gian danh gia gan nhat.
    - Sap xep va phan trang.
    - Giu nguyen thong ke CSAT toan he thong.

    Khong thay doi du lieu Ticket Module 3.
    """

    # ==========================================
    # 1. DOC THAM SO BO LOC
    # ==========================================

    keyword = request.GET.get(
        'q',
        ''
    ).strip()

    score_filter = request.GET.get(
        'score',
        ''
    ).strip()

    date_range = request.GET.get(
        'date_range',
        ''
    ).strip()

    sort_by = request.GET.get(
        'sort',
        'newest',
    ).strip()

    # ==========================================
    # 2. KIEM TRA THAM SO HOP LE
    # ==========================================

    allowed_scores = (
        '',
        '1',
        '2',
        '3',
        '4',
        '5',
        'low',
        'none',
    )

    if score_filter not in allowed_scores:
        score_filter = ''

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
            '-latest_csat_date',
            'ma_khach_hang',
        ),
        'oldest': (
            'latest_csat_date',
            'ma_khach_hang',
        ),
        'score_asc': (
            'latest_csat_score',
            'ma_khach_hang',
        ),
        'score_desc': (
            '-latest_csat_score',
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
    }

    if sort_by not in sort_options:
        sort_by = 'newest'

    # ==========================================
    # 3. CSAT MOI NHAT CUA MOI KHACH HANG
    # ==========================================

    latest_csat_query = (
        CSAT.objects
        .filter(
            ticket__khach_hang=OuterRef('pk')
        )
        .order_by(
            '-created_at',
            '-pk',
        )
    )

    # ==========================================
    # 4. DANH SACH KHACH HANG
    # ==========================================

    customers = (
        Customer.objects
        .annotate(
            latest_csat_score=Subquery(
                latest_csat_query.values(
                    'score'
                )[:1]
            ),
            latest_csat_date=Subquery(
                latest_csat_query.values(
                    'created_at'
                )[:1]
            ),
            csat_count=Count(
                'tickets__csat',
                distinct=True,
            ),
        )
    )

    # ==========================================
    # 5. TIM KIEM KHACH HANG
    # ==========================================

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

    # ==========================================
    # 6. LOC THEO DANH GIA CSAT MOI NHAT
    # ==========================================

    if score_filter == 'none':

        # Khach hang chua co danh gia CSAT.
        customers = customers.filter(
            latest_csat_score__isnull=True
        )

    elif score_filter == 'low':

        # Khach hang co CSAT gan nhat tu 1-3 sao.
        customers = customers.filter(
            latest_csat_score__lte=3,
            latest_csat_score__gte=1,
        )

    elif score_filter:

        customers = customers.filter(
            latest_csat_score=int(score_filter)
        )

    # ==========================================
    # 7. LOC THEO THOI GIAN DANH GIA
    # ==========================================

    if date_range:

        days = int(date_range)

        start_date = (
            timezone.now()
            - timedelta(days=days)
        )

        customers = customers.filter(
            latest_csat_date__gte=start_date
        )

    # ==========================================
    # 8. SAP XEP KET QUA
    # ==========================================

    customers = customers.order_by(
        *sort_options[sort_by]
    )

    # ==========================================
    # 9. THONG KE CSAT TOAN HE THONG
    # ==========================================

    csat_stats = CSAT.objects.aggregate(
        total_reviews=Count('pk'),
        average_score=Avg('score'),
        low_reviews=Count(
            'pk',
            filter=Q(score__lte=3)
        ),
    )

    # ==========================================
    # 10. PHAN TRANG
    # ==========================================

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

    # Giu lai dieu kien loc khi chuyen trang.
    query_params = request.GET.copy()

    if 'page' in query_params:
        del query_params['page']

    filter_query = query_params.urlencode()

    # ==========================================
    # 11. DU LIEU TRA VE TEMPLATE
    # ==========================================

    context = {
        'customers': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_results': paginator.count,

        'keyword': keyword,
        'score_filter': score_filter,
        'date_range': date_range,
        'sort_by': sort_by,
        'filter_query': filter_query,

        'has_filters': bool(
            keyword
            or score_filter
            or date_range
            or sort_by != 'newest'
        ),

        'total_reviews': (
            csat_stats['total_reviews']
        ),
        'average_score': (
            csat_stats['average_score']
        ),
        'low_reviews': (
            csat_stats['low_reviews']
        ),

        'active_tab': 'csat',
    }

    return render(
        request,
        'customers/csat_overview.html',
        context,
    )
