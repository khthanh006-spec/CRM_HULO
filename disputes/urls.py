from django.urls import path

from . import (
    approval_views,
    attachment_views,
    execution_views,
    plan_views,
    reconsideration_views,
    views,
)


app_name = "disputes"


urlpatterns = [
    path(
        "",
        views.dispute_home,
        name="home",
    ),
    path(
        "<int:pk>/",
        views.dispute_detail,
        name="detail",
    ),
    path(
        "<int:pk>/bang-chung/<int:attachment_pk>/xem/",
        attachment_views.dispute_attachment_preview,
        name="attachment_preview",
    ),
    path(
        "<int:pk>/bang-chung/<int:attachment_pk>/tai-ve/",
        attachment_views.dispute_attachment_download,
        name="attachment_download",
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
    path(
        "<int:pk>/thuc-hien/",
        execution_views.dispute_execute,
        name="execute",
    ),
    path(
        "<int:pk>/xem-xet-lai/",
        reconsideration_views.dispute_reconsider,
        name="reconsider",
    ),
]


from .reconsideration_result_views import dispute_reconsider_result

urlpatterns += [
    path(
        "<int:pk>/ket-qua-xem-xet-lai/",
        dispute_reconsider_result,
        name="reconsider_result",
    ),
]
