
from django.urls import path

from . import views
from . import customer_portal_views
from . import customer_profile_views
from . import manager_dashboard_views
from . import manager_customer_views
from . import cskh_dashboard_views
from . import assessor_dashboard_views


urlpatterns = [
    # ==========================================
    # ĐĂNG NHẬP
    # ==========================================

    path(
        "login/",
        views.login_view,
        name="login",
    ),

    # ==========================================
    # TRANG CHỦ THEO VAI TRÒ
    # ==========================================

    path(
        "home/",
        views.home_view,
        name="home",
    ),

    # ==========================================
    # DASHBOARD QUẢN LÝ VẬN HÀNH
    # ==========================================

    path(
        "manager/dashboard/",
        manager_dashboard_views.manager_dashboard,
        name="manager_dashboard",
    ),

    # ==========================================
    # QUẢN LÝ KHÁCH HÀNG
    # ==========================================

    path(
        "manager/customers/",
        manager_customer_views.manager_customer_list,
        name="manager_customer_list",
    ),

    path(
        "manager/customers/<int:customer_id>/",
        manager_customer_views.manager_customer_detail,
        name="manager_customer_detail",
    ),

    # ==========================================
    # DASHBOARD NHÂN VIÊN CSKH
    # ==========================================

    path(
        "cskh/dashboard/",
        cskh_dashboard_views.cskh_dashboard,
        name="cskh_dashboard",
    ),

    # ==========================================
    # MỚI: CSKH XEM THÔNG BÁO MINH CHỨNG
    # ==========================================

    path(
        "cskh/evidence-notifications/<int:request_id>/view/",
        cskh_dashboard_views.cskh_view_evidence_notification,
        name="cskh_view_evidence_notification",
    ),

    # ==========================================
    # DASHBOARD NHÂN VIÊN THẨM ĐỊNH
    # ==========================================

    path(
        "assessor/dashboard/",
        assessor_dashboard_views.assessor_dashboard,
        name="assessor_dashboard",
    ),

    # ==========================================
    # ĐĂNG XUẤT
    # ==========================================

    path(
        "logout/",
        views.logout_view,
        name="logout",
    ),

    # ==========================================
    # ĐƠN HÀNG VÀ HỖ TRỢ KHÁCH HÀNG
    # ==========================================

    path(
        "customer/orders-support/",
        customer_portal_views.customer_orders_support,
        name="customer_orders_support",
    ),

    # ==========================================
    # HỒ SƠ CÁ NHÂN KHÁCH HÀNG
    # ==========================================

    path(
        "customer/profile/",
        customer_profile_views.customer_profile,
        name="customer_profile",
    ),

    # ==========================================
    # KIỂM TRA QUYỀN CSKH
    # ==========================================

    path(
        "test-cskh/",
        views.test_cskh_view,
        name="test_cskh",
    ),
]
