
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required(login_url='login')
def support_home(request):
    return render(request, 'support/home.html')

