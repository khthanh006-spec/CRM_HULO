from django.urls import path

from . import approval_views, plan_views, views


app_name = "disputes"


urlpatterns = [
    path("", views.dispute_home, name="home"),

    path(
        "<int:pk>/",
        views.dispute_detail,
        name="detail",
    ),

    path(
        "<int:pk>/tiep-nhan/",
        views.dispute_accept,
        name="accept",
    ),

    path(
        "<int:pk>/ket-luan/",
        views.dispute_conclusion,
        name="conclusion",
    ),

    path(
        "<int:pk>/phuong-an/",
        plan_views.dispute_plan,
        name="plan",
    ),

    path(
        "<int:pk>/gui-phe-duyet/",
        approval_views.dispute_submit,
        name="submit",
    ),

    path(
        "<int:pk>/phe-duyet/",
        approval_views.dispute_review,
        name="review",
    ),
]