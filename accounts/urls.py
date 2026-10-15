
from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('home/', views.home_view, name='home'),
    path('logout/', views.logout_view, name='logout'),

    # URL tạm thời để kiểm tra phân quyền
    path(
        'test-cskh/',
        views.test_cskh_view,
        name='test_cskh'
    ),
]
