
"""
Module 5 - Customer 360°
Tổng hợp dữ liệu đơn hàng từ Module 4.

Không tạo hoặc thay đổi đơn hàng.
Không thay đổi logic của Module 4.
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q, Sum

from disputes.models import Order


def get_customer_order_360(customer):
    """
    Trả về dữ liệu đơn hàng thuộc đúng khách hàng.

    Giá trị đơn hàng được tính từ OrderItem.
    Doanh thu chỉ tính các đơn đã giao.
    Không cộng gộp các đơn khác đơn vị tiền tệ.
    """

    queryset = Order.objects.filter(
        ma_khach_hang=customer
    )

    # 1. Thống kê số đơn theo trạng thái
    statistics = queryset.aggregate(
        total=Count("pk"),
        pending=Count(
            "pk",
            filter=Q(trang_thai="CHO_XU_LY"),
        ),
        shipping=Count(
            "pk",
            filter=Q(trang_thai="DANG_GIAO"),
        ),
        delivered=Count(
            "pk",
            filter=Q(trang_thai="DA_GIAO"),
        ),
        cancelled=Count(
            "pk",
            filter=Q(trang_thai="DA_HUY"),
        ),
    )

    # 2. Tổng giá trị đơn đã giao, phân theo tiền tệ
    revenue_rows = (
        queryset
        .filter(trang_thai="DA_GIAO")
        .values("don_vi_tien_te")
        .annotate(
            total=Sum("items__gia_tri_da_thanh_toan")
        )
        .order_by("don_vi_tien_te")
    )

    revenue_by_currency = [
        {
            "currency": row["don_vi_tien_te"],
            "amount": row["total"] or Decimal("0.00"),
        }
        for row in revenue_rows
    ]

    # 3. Lịch sử 20 đơn hàng gần nhất
    recent_orders = list(
        queryset
        .prefetch_related("items")
        .order_by("-thoi_diem_dat", "-pk")[:20]
    )

    order_rows = []

    for order in recent_orders:
        items = list(order.items.all())

        total_amount = sum(
            (
                item.gia_tri_da_thanh_toan
                for item in items
            ),
            Decimal("0.00"),
        )

        order_rows.append({
            "id": order.pk,
            "code": order.so_don_hang,
            "created_at": order.thoi_diem_dat,
            "status": order.trang_thai,
            "status_display": order.get_trang_thai_display(),
            "currency": order.don_vi_tien_te,
            "total_amount": total_amount,
            "items": items,
            "item_count": len(items),
        })

    # 4. Đơn hàng mới nhất
    latest_order = order_rows[0] if order_rows else None

    return {
        "order_count": statistics["total"],
        "order_pending_count": statistics["pending"],
        "order_shipping_count": statistics["shipping"],
        "order_delivered_count": statistics["delivered"],
        "order_cancelled_count": statistics["cancelled"],
        "order_revenue_by_currency": revenue_by_currency,
        "order_rows": order_rows,
        "latest_order": latest_order,
    }
