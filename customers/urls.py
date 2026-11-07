
from django.urls import path

from . import (
    views,
    csat_overview_views,
    after_sales_views,
    customer_offers_views,
    customer_list_views,
    loyalty_overview_views,
)

app_name = 'customers'

urlpatterns = [
    path(
        '',
        views.customer_home,
        name='home',
    ),

    path(
        'list/',
        customer_list_views.customer_list,
        name='list',
    ),

    path(
        'csat/',
        csat_overview_views.csat_overview,
        name='csat_overview',
    ),

    path(
        '<int:customer_id>/',
        views.customer_detail,
        name='detail',
    ),

    path(
        '<int:customer_id>/care-records/add/',
        views.add_care_record,
        name='add_care_record',
    ),

    path(
        '<int:customer_id>/csat-care/',
        views.csat_care,
        name='csat_care',
    ),

    path(
        'tickets/<int:ticket_id>/csat/',
        views.submit_csat,
        name='submit_csat',
    ),

    path(
        '<int:customer_id>/loyalty/',
        views.loyalty_detail,
        name='loyalty_detail',
    ),

    path(
        '<int:customer_id>/loyalty/adjust-demo/',
        views.loyalty_adjust_demo,
        name='loyalty_adjust_demo',
    ),

    # LOYALTY - BO LOC NANG CAO
    path(
        'loyalty/',
        loyalty_overview_views.loyalty_overview,
        name='loyalty_overview',
    ),

    path(
        'after-sales/',
        after_sales_views.after_sales_overview,
        name='after_sales_overview',
    ),

    path(
        'after-sales/vouchers/<int:benefit_id>/issue/',
        after_sales_views.issue_voucher,
        name='issue_voucher',
    ),

    path(
        'my-vouchers/',
        customer_offers_views.my_offers,
        name='my_vouchers',
    ),

    path(
        'after-sales/history/',
        after_sales_views.voucher_history,
        name='voucher_history',
    ),

    path(
        'after-sales/retention/sync/',
        after_sales_views.sync_retention_cases,
        name='sync_retention_cases',
    ),

    path(
        'after-sales/retention/<int:case_id>/',
        after_sales_views.retention_detail,
        name='retention_detail',
    ),

    path(
        '<int:customer_id>/csat-care/vouchers/',
        after_sales_views.choose_csat_voucher,
        name='choose_csat_voucher',
    ),
]
