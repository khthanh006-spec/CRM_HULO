
from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    # Trang chủ Trung tâm hỗ trợ
    path('', views.support_home, name='home'),

    # Trang chi tiết FAQ và ghi nhận lượt xem
    path(
        'faq/<int:faq_id>/',
        views.faq_detail,
        name='faq_detail'
    ),

    # Tiếp nhận đánh giá hữu ích / không hữu ích
    path(
        'faq/<int:faq_id>/feedback/',
        views.faq_feedback,
        name='faq_feedback'
    ),
]
