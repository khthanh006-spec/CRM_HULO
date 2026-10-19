

from django.shortcuts import render, get_object_or_404
from django.db.models import Q

from accounts.permissions import role_required
from .models import Customer


@role_required('CSKH', 'ASSESSOR', 'MANAGER')
def customer_home(request):
    return render(request, 'customers/home.html')


@role_required('CSKH', 'MANAGER')
def customer_list(request):
    # Lấy từ khóa tìm kiếm
    keyword = request.GET.get('q', '').strip()

    # Lấy danh sách khách hàng
    customers = Customer.objects.all().order_by('ma_khach_hang')

    # Tìm theo tên, email hoặc mã khách hàng
    if keyword:
        conditions = (
            Q(ho_ten__icontains=keyword) |
            Q(email__icontains=keyword)
        )

        if keyword.isdecimal():
            conditions |= Q(ma_khach_hang=int(keyword))

        customers = customers.filter(conditions)

    context = {
        'customers': customers,
        'keyword': keyword,
    }

    return render(request, 'customers/customer_list.html', context)
@role_required('CSKH', 'MANAGER')
def customer_detail(request, customer_id):
    customer = get_object_or_404(
        Customer,
        pk=customer_id
    )

    context = {
        'customer': customer,
    }

    return render(
        request,
        'customers/customer_detail.html',
        context
    )
