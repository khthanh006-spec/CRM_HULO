
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from accounts.permissions import get_user_role
from customers.models import Customer
from disputes.models import Order
from tickets.models import Ticket


@login_required(login_url="login")
def customer_orders_support(request):
    """
    Trang Đơn hàng & Hỗ trợ dành cho khách hàng.
    Chỉ hiển thị Order và Ticket thuộc tài khoản đăng nhập.
    """

    if get_user_role(request.user) != "CUSTOMER":
        raise PermissionDenied(
            "Chỉ khách hàng được truy cập trang này."
        )

    customer = Customer.objects.filter(
        ma_tai_khoan=request.user
    ).first()

    orders = Order.objects.none()
    tickets = Ticket.objects.none()

    if customer is not None:
        orders = (
            Order.objects
            .filter(ma_khach_hang=customer)
            .prefetch_related("items")
            .order_by("-thoi_diem_dat")
        )

        tickets = (
            Ticket.objects
            .filter(khach_hang=customer)
            .order_by("-pk")
        )

    active_tab = request.GET.get("tab", "orders")

    if active_tab not in ("orders", "tickets"):
        active_tab = "orders"

    return render(
        request,
        "accounts/customer_orders_support.html",
        {
            "customer": customer,
            "orders": orders,
            "tickets": tickets,
            "active_tab": active_tab,
        }
    )
