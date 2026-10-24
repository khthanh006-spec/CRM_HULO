
from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [

    # Trang chủ Module 5
    path(
        '',
        views.customer_home,
        name='home'
    ),

    # Danh sách khách hàng
    path(
        'list/',
        views.customer_list,
        name='list'
    ),

    # Hồ sơ Customer 360
    path(
        '<int:customer_id>/',
        views.customer_detail,
        name='detail'
    ),

    # Lưu ghi chú / chăm sóc
    path(
        '<int:customer_id>/care-records/add/',
        views.add_care_record,
        name='add_care_record'
    ),
    path(
         '<int:customer_id>/csat-care/',
         views.csat_care,
         name='csat_care'
),
]

