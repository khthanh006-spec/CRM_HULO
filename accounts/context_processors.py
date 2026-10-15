
from .permissions import get_user_role


def user_role(request):
    """
    Cung cấp vai trò người dùng
    cho tất cả Django Templates.
    """

    if request.user.is_authenticated:
        role = get_user_role(request.user)
    else:
        role = None

    return {
        'user_role': role
    }
