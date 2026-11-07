
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import redirect, render

from accounts.permissions import get_user_role
from customers.models import (
    Customer,
    CSAT,
    LoyaltyAccount,
    LoyaltyTransaction,
    LoyaltyRedemption,
)
from disputes.models import Order
from tickets.models import Ticket


@login_required(login_url="login")
def customer_profile(request):
    """
    Tài khoản của tôi:
    - Thông tin cá nhân
    - Lịch sử hoạt động

    Chỉ khách hàng được truy cập.
    Dữ liệu luôn được lọc theo tài khoản đăng nhập.
    """

    if get_user_role(request.user) != "CUSTOMER":
        raise PermissionDenied(
            "Chỉ khách hàng được truy cập trang này."
        )

    customer = Customer.objects.filter(
        ma_tai_khoan=request.user
    ).first()

    if customer is None:
        raise PermissionDenied(
            "Tài khoản chưa được liên kết với hồ sơ khách hàng."
        )

    active_tab = request.GET.get("tab", "profile")

    if active_tab not in ("profile", "history"):
        active_tab = "profile"

    form_values = None

    # ==========================================
    # CẬP NHẬT THÔNG TIN CÁ NHÂN
    # ==========================================

    if request.method == "POST":
        active_tab = "profile"

        form_values = {
            "ho_ten": request.POST.get(
                "ho_ten", ""
            ).strip(),
            "email": request.POST.get(
                "email", ""
            ).strip(),
            "so_dien_thoai": request.POST.get(
                "so_dien_thoai", ""
            ).strip(),
            "dia_chi_mac_dinh": request.POST.get(
                "dia_chi_mac_dinh", ""
            ).strip(),
        }

        ho_ten = form_values["ho_ten"]
        email = form_values["email"]
        so_dien_thoai = form_values["so_dien_thoai"]
        dia_chi = form_values["dia_chi_mac_dinh"]

        if not ho_ten:
            messages.error(
                request,
                "Họ và tên không được để trống."
            )

        elif not email:
            messages.error(
                request,
                "Email không được để trống."
            )

        elif Customer.objects.filter(
            email__iexact=email
        ).exclude(
            pk=customer.pk
        ).exists():
            messages.error(
                request,
                "Email này đã được sử dụng."
            )

        else:
            try:
                with transaction.atomic():
                    customer.ho_ten = ho_ten
                    customer.email = email
                    customer.so_dien_thoai = (
                        so_dien_thoai or None
                    )
                    customer.dia_chi_mac_dinh = (
                        dia_chi or None
                    )

                    customer.full_clean()
                    customer.save()

                messages.success(
                    request,
                    "Cập nhật thông tin cá nhân thành công!"
                )

                return redirect(
                    "customer_profile"
                )

            except ValidationError as exc:
                error_text = "; ".join(
                    exc.messages
                )

                messages.error(
                    request,
                    f"Thông tin chưa hợp lệ: {error_text}"
                )

            except IntegrityError:
                messages.error(
                    request,
                    "Dữ liệu bị trùng hoặc không hợp lệ."
                )

    # ==========================================
    # LỊCH SỬ ĐƠN HÀNG
    # ==========================================

    orders = (
        Order.objects
        .filter(ma_khach_hang=customer)
        .annotate(
            total_amount=Sum(
                "items__gia_tri_da_thanh_toan"
            )
        )
        .order_by("-thoi_diem_dat", "-pk")
    )

    # ==========================================
    # LỊCH SỬ TICKET
    # ==========================================

    tickets = (
        Ticket.objects
        .filter(khach_hang=customer)
        .order_by("-thoi_diem_tao", "-pk")
    )

    # ==========================================
    # LỊCH SỬ CSAT
    # ==========================================

    csat_reviews = (
        CSAT.objects
        .filter(ticket__khach_hang=customer)
        .select_related("ticket")
        .order_by("-created_at", "-pk")
    )

    # ==========================================
    # TÀI KHOẢN LOYALTY
    # ==========================================

    loyalty_account = (
        LoyaltyAccount.objects
        .filter(customer=customer)
        .select_related("tier")
        .first()
    )

    loyalty_transactions = (
        LoyaltyTransaction.objects
        .filter(account__customer=customer)
        .order_by("-created_at", "-pk")
    )

    # ==========================================
    # LỊCH SỬ VOUCHER ĐÃ ĐỔI
    # ==========================================

    redemptions = (
        LoyaltyRedemption.objects
        .filter(
            transaction__account__customer=customer
        )
        .select_related("transaction", "reward")
        .order_by("-issued_at", "-pk")
    )

    context = {
        "customer": customer,
        "active_tab": active_tab,
        "form_values": form_values,
        "orders": orders,
        "tickets": tickets,
        "csat_reviews": csat_reviews,
        "loyalty_account": loyalty_account,
        "loyalty_transactions": loyalty_transactions,
        "redemptions": redemptions,
    }

    return render(
        request,
        "accounts/customer_profile.html",
        context,
    )
