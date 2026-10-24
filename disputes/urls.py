from django.urls import path
from . import views

app_name = "disputes"

urlpatterns = [
    path("", views.dispute_home, name="home"),
    path("<int:pk>/", views.dispute_detail, name="detail"),
]