
from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    path('', views.ticket_home, name='home'),
]

