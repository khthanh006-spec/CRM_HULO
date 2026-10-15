
from accounts.models import Staff
from customers.models import Customer


def get_user_role(user):
    # Người dùng chưa đăng nhập
    if not user.is_authenticated:
        return None

    # Tài khoản quản trị hệ thống
    if user.is_superuser:
        return 'ADMIN'

    # Kiểm tra hồ sơ nhân viên
    try:
        staff = Staff.objects.get(ma_tai_khoan=user)
        return staff.vai_tro
    except Staff.DoesNotExist:
        pass

    # Kiểm tra hồ sơ khách hàng
    if Customer.objects.filter(ma_tai_khoan=user).exists():
        return 'CUSTOMER'

    # Tài khoản chưa có hồ sơ
    return 'UNASSIGNED'


from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def role_required(*allowed_roles):
    """
    Chỉ cho phép những vai trò được chỉ định
    truy cập vào View.
    """

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            # Chưa đăng nhập -> chuyển đến Login
            if not request.user.is_authenticated:
                return redirect_to_login(
                    request.get_full_path(),
                    login_url='login'
                )

            # Xác định vai trò người dùng
            role = get_user_role(request.user)

            # Không thuộc vai trò được phép -> lỗi 403
            if role not in allowed_roles:
                raise PermissionDenied(
                    "Bạn không có quyền truy cập chức năng này."
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
