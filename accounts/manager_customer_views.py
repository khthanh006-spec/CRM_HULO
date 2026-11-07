
import re
from collections import defaultdict

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from accounts.permissions import role_required
from customers.models import Customer
from disputes.models import (
    DisputeCase,
    Order,
    OrderItem,
)
from tickets.models import Ticket


# Nhận diện mã đơn trong yêu cầu Chatbot.
# Ví dụ:
# Mã đơn hàng: HULO-DEMO-004
ORDER_CODE_PATTERN = re.compile(
    r"^\s*Mã đơn hàng:\s*([A-Za-z0-9_-]+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_order_code(ticket):
    """
    Đọc mã đơn hàng từ nội dung Ticket.

    Không tự đoán mã đơn hàng dựa trên
    tiêu đề hoặc tên khách hàng.
    """
    content = ticket.noi_dung or ""

    match = ORDER_CODE_PATTERN.search(content)

    if match:
        return match.group(1).strip()

    return None


def get_customer_counts():
    """
    Đếm số đơn hàng và Ticket theo khách hàng.

    Tách truy vấn để tránh nhân đôi số lượng
    khi JOIN nhiều bảng.
    """

    order_counts = {
        item["ma_khach_hang_id"]: item["total"]
        for item in (
            Order.objects
            .values("ma_khach_hang_id")
            .annotate(total=Count("pk"))
        )
    }

    ticket_counts = {
        item["khach_hang_id"]: item["total"]
        for item in (
            Ticket.objects
            .values("khach_hang_id")
            .annotate(total=Count("pk"))
        )
    }

    return order_counts, ticket_counts


# ==================================================
# DANH SÁCH KHÁCH HÀNG - MANAGER
# ==================================================

@role_required("MANAGER")
def manager_customer_list(request):

    keyword = request.GET.get(
        "q",
        "",
    ).strip()

    customers = (
        Customer.objects
        .all()
        .order_by("ma_khach_hang")
    )

    if keyword:
        condition = (
            Q(ho_ten__icontains=keyword)
            | Q(email__icontains=keyword)
            | Q(so_dien_thoai__icontains=keyword)
            | Q(ma_tai_khoan__username__icontains=keyword)
        )

        if keyword.isdecimal():
            condition |= Q(
                ma_khach_hang=int(keyword)
            )

        customers = customers.filter(condition)

    page_obj = Paginator(
        customers,
        15,
    ).get_page(
        request.GET.get("page")
    )

    order_counts, ticket_counts = (
        get_customer_counts()
    )

    customer_rows = []

    for customer in page_obj.object_list:
        customer_rows.append({
            "customer": customer,
            "order_count": order_counts.get(
                customer.pk, 0
            ),
            "ticket_count": ticket_counts.get(
                customer.pk, 0
            ),
        })

    context = {
        "customer_rows": customer_rows,
        "page_obj": page_obj,
        "keyword": keyword,
        "total_customers": Customer.objects.count(),
        "total_orders": Order.objects.count(),
        "total_tickets": Ticket.objects.count(),
    }

    return render(
        request,
        "accounts/manager_customer_list.html",
        context,
    )


# ==================================================
# CHI TIẾT KHÁCH HÀNG - MANAGER
# ==================================================

@role_required("MANAGER")
def manager_customer_detail(request, customer_id):

    customer = get_object_or_404(
        Customer.objects.select_related(
            "ma_tai_khoan"
        ),
        pk=customer_id,
    )

    # 1. Chỉ lấy đơn của khách hàng đang xem.
    orders = list(
        Order.objects
        .filter(ma_khach_hang=customer)
        .order_by(
            "-thoi_diem_dat",
            "-pk",
        )
    )

    order_ids = [
        order.pk
        for order in orders
    ]

    order_codes = {
        order.so_don_hang.upper(): order
        for order in orders
    }

    # 2. Lấy sản phẩm của các đơn hàng.
    order_items = (
        OrderItem.objects
        .filter(
            ma_don_hang_id__in=order_ids
        )
        .order_by("pk")
    )

    items_by_order = defaultdict(list)

    for item in order_items:
        items_by_order[
            item.ma_don_hang_id
        ].append(item)

    # 3. Lấy toàn bộ Ticket của khách hàng.
    tickets = list(
        Ticket.objects
        .filter(khach_hang=customer)
        .select_related(
            "nguoi_phu_trach",
            "danh_muc",
        )
        .order_by(
            "-thoi_diem_tao",
            "-pk",
        )
    )

    ticket_ids = [
        ticket.pk
        for ticket in tickets
    ]

    # 4. Lấy hồ sơ thẩm định gắn với Ticket.
    dispute_map = {
        dispute.ma_ticket_id: dispute
        for dispute in (
            DisputeCase.objects
            .filter(
                ma_ticket_id__in=ticket_ids
            )
            .select_related(
                "ma_nhan_vien_tham_dinh"
            )
        )
    }

    # 5. Ghép Ticket vào đúng đơn hàng.
    tickets_by_order = defaultdict(list)

    unlinked_tickets = []

    for ticket in tickets:
        code = extract_order_code(ticket)

        # Chỉ ghép nếu mã đơn thuộc chính
        # khách hàng hiện tại.
        order = (
            order_codes.get(code.upper())
            if code
            else None
        )

        ticket_info = {
            "ticket": ticket,
            "dispute": dispute_map.get(
                ticket.pk
            ),
            "order_code": code,
        }

        if order is not None:
            tickets_by_order[
                order.pk
            ].append(ticket_info)
        else:
            # Ticket không ghi mã đơn,
            # sai mã hoặc không thuộc khách này.
            unlinked_tickets.append(ticket_info)

    # 6. Xây dựng cấu trúc hiển thị:
    # Khách hàng -> Đơn hàng -> Ticket.
    order_rows = []

    for order in orders:
        order_rows.append({
            "order": order,
            "items": items_by_order.get(
                order.pk,
                [],
            ),
            "tickets": tickets_by_order.get(
                order.pk,
                [],
            ),
            "ticket_count": len(
                tickets_by_order.get(
                    order.pk,
                    [],
                )
            ),
        })

    context = {
        "customer": customer,
        "order_rows": order_rows,
        "unlinked_tickets": unlinked_tickets,
        "total_orders": len(orders),
        "total_tickets": len(tickets),
        "linked_ticket_count": (
            len(tickets) - len(unlinked_tickets)
        ),
        "unlinked_ticket_count": len(
            unlinked_tickets
        ),
    }

    return render(
        request,
        "accounts/manager_customer_detail.html",
        context,
    )
