
from django.shortcuts import render

from accounts.permissions import role_required


@role_required('CSKH', 'ASSESSOR', 'MANAGER')
def customer_home(request):
    return render(request, 'customers/home.html')
