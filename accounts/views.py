
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .permissions import get_user_role, role_required


def redirect_after_login(user):
    """
    Điều hướng sau đăng nhập theo vai trò.

    ADMIN:
        Django Admin.

    MANAGER:
        Dashboard quản lý vận hành.

    CSKH:
        Dashboard CSKH cá nhân.

    ASSESSOR:
        Dashboard thẩm định cá nhân.

    CUSTOMER:
        Trung tâm trợ giúp.
    """

    role = get_user_role(user)

    if role == "ADMIN":
        return redirect("admin:index")

    if role == "MANAGER":
        return redirect("manager_dashboard")

    if role == "CSKH":
        return redirect("cskh_dashboard")

    if role == "ASSESSOR":
        return redirect("assessor_dashboard")

    if role == "CUSTOMER":
        return redirect("support:home")

    return redirect("home")


# ==================================================
# ĐĂNG NHẬP
# ==================================================

def login_view(request):

    if request.user.is_authenticated:
        return redirect_after_login(request.user)

    error_message = None

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            login(request, user)
            return redirect_after_login(user)

        error_message = (
            "Tên đăng nhập hoặc mật khẩu không đúng."
        )

    return render(
        request,
        "accounts/login.html",
        {
            "error_message": error_message,
        },
    )


# ==================================================
# TRANG CHỦ THEO VAI TRÒ
# ==================================================

@login_required(login_url="login")
def home_view(request):

    role = get_user_role(request.user)

    if role == "ADMIN":
        return redirect("admin:index")

    if role == "MANAGER":
        return redirect("manager_dashboard")

    if role == "CSKH":
        return redirect("cskh_dashboard")

    if role == "ASSESSOR":
        return redirect("assessor_dashboard")

    if role == "CUSTOMER":
        return redirect("support:home")

    role_names = {
        "ADMIN": "Quản trị hệ thống",
        "CUSTOMER": "Khách hàng",
        "CSKH": "Nhân viên chăm sóc khách hàng",
        "ASSESSOR": "Nhân viên thẩm định",
        "MANAGER": "Quản lý vận hành",
        "UNASSIGNED": "Chưa được phân quyền",
    }

    role_display = role_names.get(
        role,
        "Không xác định",
    )

    return render(
        request,
        "accounts/home.html",
        {
            "role": role,
            "role_display": role_display,
        },
    )


# ==================================================
# ĐĂNG XUẤT
# ==================================================

@require_POST
@login_required(login_url="login")
def logout_view(request):
    logout(request)
    return redirect("login")


# ==================================================
# KIỂM TRA QUYỀN CSKH
# ==================================================

@role_required("CSKH")
def test_cskh_view(request):
    return HttpResponse(
        "<h1>TRANG KIỂM TRA QUYỀN CSKH</h1>"
        "<p>Bạn có quyền truy cập chức năng này.</p>"
    )
