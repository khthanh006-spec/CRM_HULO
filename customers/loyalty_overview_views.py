
# =========================================================
# CRM HULO - MODULE 5
# TONG QUAN LOYALTY - BO LOC NANG CAO
# =========================================================

from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import render

from accounts.permissions import role_required

from .models import LoyaltyAccount, LoyaltyTier


@role_required('CSKH', 'MANAGER')
def loyalty_overview(request):
    """
    Quan ly danh sach tai khoan Loyalty.

    - Tim kiem khach hang theo ma, ten, email, SDT.
    - Loc theo hang thanh vien.
    - Loc theo so diem hien co.
    - Sap xep danh sach.
    - Phan trang va giu lai bo loc.
    - Giu nguyen thong ke tren toan he thong.

    Chi doc du lieu, khong thay doi giao dich diem.
    """

    # ==========================================
    # 1. DOC THAM SO BO LOC
    # ==========================================

    keyword = request.GET.get(
        'q', ''
    ).strip()

    tier_id = request.GET.get(
        'tier', ''
    ).strip()

    points_range = request.GET.get(
        'points_range', ''
    ).strip()

    sort_by = request.GET.get(
        'sort', 'newest'
    ).strip()

    # ==========================================
    # 2. KIEM TRA THAM SO HOP LE
    # ==========================================

    valid_points_ranges = (
        '',
        'zero',
        '1_499',
        '500_999',
        '1000_4999',
        '5000_plus',
    )

    if points_range not in valid_points_ranges:
        points_range = ''

    sort_options = {
        'newest': (
            '-created_at',
            '-pk',
        ),
        'oldest': (
            'created_at',
            'pk',
        ),
        'points_desc': (
            '-points_balance',
            'pk',
        ),
        'points_asc': (
            'points_balance',
            'pk',
        ),
        'earned_desc': (
            '-total_points_earned',
            'pk',
        ),
        'earned_asc': (
            'total_points_earned',
            'pk',
        ),
        'name_asc': (
            'customer__ho_ten',
            'pk',
        ),
        'name_desc': (
            '-customer__ho_ten',
            'pk',
        ),
        'code_asc': (
            'customer__ma_khach_hang',
            'pk',
        ),
    }

    if sort_by not in sort_options:
        sort_by = 'newest'

    # ==========================================
    # 3. LAY CAC HANG THANH VIEN
    # ==========================================

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

    # ==========================================
    # 4. THONG KE TOAN HE THONG
    # ==========================================

    all_accounts = LoyaltyAccount.objects.all()

    total_accounts = all_accounts.count()

    total_points_balance = (
        all_accounts.aggregate(
            total=Sum('points_balance')
        )['total']
        or 0
    )

    # ==========================================
    # 5. QUERYSET LOYALTY
    # ==========================================

    loyalty_accounts = (
        all_accounts
        .select_related(
            'customer',
            'tier',
        )
    )

    # ==========================================
    # 6. TIM KIEM KHACH HANG
    # ==========================================

    if keyword:
        conditions = (
            Q(
                customer__ho_ten__icontains=keyword
            )
            | Q(
                customer__email__icontains=keyword
            )
            | Q(
                customer__so_dien_thoai__icontains=keyword
            )
        )

        if keyword.isdecimal():
            conditions |= Q(
                customer__ma_khach_hang=int(keyword)
            )

        loyalty_accounts = loyalty_accounts.filter(
            conditions
        )

    # ==========================================
    # 7. LOC THEO HANG THANH VIEN
    # ==========================================

    if tier_id == 'none':
        loyalty_accounts = loyalty_accounts.filter(
            tier__isnull=True
        )

    elif tier_id:
        loyalty_accounts = loyalty_accounts.filter(
            tier_id=int(tier_id)
        )

    # ==========================================
    # 8. LOC THEO DIEM HIEN CO
    # ==========================================

    if points_range == 'zero':
        loyalty_accounts = loyalty_accounts.filter(
            points_balance=0
        )

    elif points_range == '1_499':
        loyalty_accounts = loyalty_accounts.filter(
            points_balance__gte=1,
            points_balance__lte=499,
        )

    elif points_range == '500_999':
        loyalty_accounts = loyalty_accounts.filter(
            points_balance__gte=500,
            points_balance__lte=999,
        )

    elif points_range == '1000_4999':
        loyalty_accounts = loyalty_accounts.filter(
            points_balance__gte=1000,
            points_balance__lte=4999,
        )

    elif points_range == '5000_plus':
        loyalty_accounts = loyalty_accounts.filter(
            points_balance__gte=5000
        )

    # ==========================================
    # 9. SAP XEP
    # ==========================================

    loyalty_accounts = loyalty_accounts.order_by(
        *sort_options[sort_by]
    )

    # ==========================================
    # 10. PHAN TRANG
    # ==========================================

    paginator = Paginator(
        loyalty_accounts,
        10,
    )

    page_number = request.GET.get(
        'page',
        1,
    )

    page_obj = paginator.get_page(
        page_number
    )

    # Giu cac dieu kien loc khi chuyen trang.
    query_params = request.GET.copy()

    if 'page' in query_params:
        del query_params['page']

    filter_query = query_params.urlencode()

    # ==========================================
    # 11. DU LIEU TRA VE TEMPLATE
    # ==========================================

    context = {
        'loyalty_accounts': page_obj,
        'page_obj': page_obj,
        'total_results': paginator.count,
        'total_accounts': total_accounts,
        'total_points_balance': total_points_balance,
        'keyword': keyword,
        'tier_id': tier_id,
        'points_range': points_range,
        'sort_by': sort_by,
        'tiers': tiers,
        'filter_query': filter_query,
        'has_filters': bool(
            keyword
            or tier_id
            or points_range
            or sort_by != 'newest'
        ),
    }

    return render(
        request,
        'customers/loyalty_overview.html',
        context,
    )
