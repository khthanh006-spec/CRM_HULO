
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponse
from .permissions import get_user_role


# Chức năng đăng nhập
def login_view(request):

    # Nếu đã đăng nhập thì chuyển đến Home
    if request.user.is_authenticated:
        return redirect('home')

    error_message = None

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            error_message = 'Tên đăng nhập hoặc mật khẩu không đúng.'

    return render(
        request,
        'accounts/login.html',
        {'error_message': error_message}
    )


# Trang Home sau khi đăng nhập

@login_required(login_url='login')
def home_view(request):

    role = get_user_role(request.user)

    role_names = {
        'ADMIN': 'Quản trị hệ thống',
        'CUSTOMER': 'Khách hàng',
        'CSKH': 'Nhân viên CSKH',
        'ASSESSOR': 'Nhân viên thẩm định',
        'MANAGER': 'Quản lý',
        'UNASSIGNED': 'Chưa được phân quyền',
    }

    role_display = role_names.get(
        role, 'Không xác định'
    )

    return render(
        request,
        'accounts/home.html',
        {
            'role': role,
            'role_display': role_display,
        }
    )



from django.contrib.auth import logout
from django.views.decorators.http import require_POST


@require_POST
@login_required(login_url='login')
def logout_view(request):
    logout(request)
    return redirect('login')


from accounts.permissions import role_required


@role_required('CSKH')
def test_cskh_view(request):
    return HttpResponse(
        "<h1>TRANG KIỂM TRA QUYỀN CSKH</h1>"
        "<p>Bạn có quyền truy cập chức năng này.</p>"
    )
