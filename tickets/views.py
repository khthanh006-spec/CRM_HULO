
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required(login_url='login')
def ticket_home(request):
    return render(request, 'tickets/home.html')
