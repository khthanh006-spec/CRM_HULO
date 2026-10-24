
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.db.models import Q

from accounts.permissions import role_required
from .forms import CareInteractionForm
from .models import Customer, LoyaltyAccount, CareRecord


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

    # 1. Lấy thông tin khách hàng
    customer = get_object_or_404(
        Customer,
        pk=customer_id
    )

    # 2. Lấy tài khoản Loyalty
    loyalty_account = (
        LoyaltyAccount.objects
        .select_related('tier')
        .filter(customer=customer)
        .first()
    )

    # 3. Lấy lịch sử giao dịch điểm
    if loyalty_account:
        transactions = (
            loyalty_account.transactions
            .all()
            .order_by('-created_at', '-pk')
        )
    else:
        transactions = []

    # 4. Lấy lịch sử chăm sóc
    care_records = (
        CareRecord.objects
        .filter(customer=customer)
        .select_related('created_by')
    )

    # 5. Gửi dữ liệu sang HTML
    context = {
        'customer': customer,
        'loyalty_account': loyalty_account,
        'transactions': transactions,
        'care_records': care_records,
    }

    return render(
        request,
        'customers/customer_detail.html',
        context
    )

# ==========================================
# LUU HOAT DONG CHAM SOC / GHI CHU
# ==========================================

@role_required('CSKH', 'MANAGER')
@require_POST
def add_care_record(request, customer_id):

    customer = get_object_or_404(
        Customer,
        pk=customer_id
    )

    # Lấy dữ liệu từ biểu mẫu
    care_type = request.POST.get(
        'care_type',
        CareRecord.CareType.NOTE
    )

    content = (
        request.POST.get('content') or ''
    ).strip()

    # Kiểm tra dữ liệu
    if care_type not in CareRecord.CareType.values:
        messages.error(
            request,
            'Hình thức chăm sóc không hợp lệ.'
        )

    elif not content:
        messages.error(
            request,
            'Vui lòng nhập nội dung chăm sóc.'
        )

    elif len(content) > 500:
        messages.error(
            request,
            'Nội dung không được quá 500 ký tự.'
        )

    else:
        # Lưu vào database
        CareRecord.objects.create(
            customer=customer,
            created_by=request.user,
            care_type=care_type,
            content=content
        )

        messages.success(
            request,
            'Đã lưu nội dung chăm sóc thành công.'
        )

    return redirect(
        'customers:detail',
        customer_id=customer.pk
    )

# ==========================================
# MODULE 5 - TRANG CHAM SOC CSAT THAP
# ==========================================


@role_required('CSKH', 'MANAGER')
def csat_care(request, customer_id):

    # 1. Lấy khách hàng cần chăm sóc
    customer = get_object_or_404(
        Customer,
        pk=customer_id
    )

    # 2. Nếu nhân viên nhấn Lưu
    if request.method == 'POST':

        form = CareInteractionForm(request.POST)

        if form.is_valid():

            # Tạo bản ghi nhưng chưa lưu
            care_record = form.save(commit=False)

            # Gắn khách hàng
            care_record.customer = customer

            # Gắn nhân viên thực hiện
            care_record.created_by = request.user

            # Lưu database
            care_record.save()

            messages.success(
                request,
                'Đã lưu hoạt động chăm sóc thành công.'
            )

            return redirect(
                'customers:csat_care',
                customer_id=customer.pk
            )

    else:
        # Khi mới mở trang
        form = CareInteractionForm(
            initial={
                'care_type': CareRecord.CareType.CALL
            }
        )

    # 3. Lấy lịch sử chăm sóc
    care_records = (
        CareRecord.objects
        .filter(customer=customer)
        .select_related('created_by')
        .order_by('-created_at', '-pk')
    )

    # 4. Gửi sang HTML
    context = {
        'customer': customer,
        'form': form,
        'care_records': care_records,
    }

    return render(
        request,
        'customers/csat_care.html',
        context
    )
