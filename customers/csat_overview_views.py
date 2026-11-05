
# =========================================================
# CRM HULO - MODULE 5
# TRANG TONG HOP CSAT & CHAM SOC KHACH HANG
# =========================================================

from django.db.models import (
    Q,
    Avg,
    Count,
    OuterRef,
    Subquery,
)

from django.shortcuts import render

from accounts.permissions import role_required

from .models import Customer, CSAT


@role_required('CSKH', 'MANAGER')
def csat_overview(request):
    """
    Trang tong hop CSAT va cham soc khach hang.

    - Tim kiem khach hang
    - Hien thi CSAT gan nhat
    - Thong ke danh gia CSAT
    - Dieu huong den trang cham soc chi tiet

    Khong thay doi du lieu Ticket Module 3.
    """

    # 1. Lay tu khoa tim kiem
    keyword = request.GET.get('q', '').strip()

    # 2. Truy van CSAT moi nhat cua moi khach hang
    latest_csat_query = (
        CSAT.objects
        .filter(
            ticket__khach_hang=OuterRef('pk')
        )
        .order_by('-created_at', '-pk')
    )

    # 3. Lay danh sach khach hang
    customers = (
        Customer.objects
        .annotate(
            latest_csat_score=Subquery(
                latest_csat_query.values('score')[:1]
            ),
            csat_count=Count(
                'tickets__csat',
                distinct=True
            )
        )
        .order_by('ma_khach_hang')
    )

    # 4. Tim kiem khach hang
    if keyword:
        conditions = (
            Q(ho_ten__icontains=keyword)
            | Q(email__icontains=keyword)
        )

        if keyword.isdecimal():
            conditions |= Q(
                ma_khach_hang=int(keyword)
            )

        customers = customers.filter(conditions)

    # 5. Thong ke CSAT tren toan he thong
    csat_stats = CSAT.objects.aggregate(
        total_reviews=Count('pk'),
        average_score=Avg('score'),
        low_reviews=Count(
            'pk',
            filter=Q(score__lte=3)
        )
    )

    # 6. Truyen du lieu sang template
    context = {
        'customers': customers,
        'keyword': keyword,
        'total_reviews': csat_stats['total_reviews'],
        'average_score': csat_stats['average_score'],
        'low_reviews': csat_stats['low_reviews'],
        'active_tab': 'csat',
    }

    return render(
        request,
        'customers/csat_overview.html',
        context
    )
