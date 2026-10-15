
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Trang quản trị Django
    path('admin/', admin.site.urls),

    # Tài khoản và phân quyền dùng chung
    path('accounts/', include('accounts.urls')),

    # Module 1: Trung tâm hỗ trợ / FAQ
    path('support/', include('support.urls')),

    # Module 2: Chatbot
    path('chatbot/', include('chatbot.urls')),

    # Module 3: Quản lý Ticket và SLA
    path('tickets/', include('tickets.urls')),

    # Module 4: Xử lý khiếu nại
    path('disputes/', include('disputes.urls')),

    # Module 5: Customer 360, CSAT và Loyalty
    path('customers/', include('customers.urls')),
]
