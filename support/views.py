from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count
from django.views.decorators.http import require_POST

from .models import (
    FAQCategory,
    FAQArticle,
    FAQInteraction,
    FAQFeedback,
)


def support_home(request):
    """
    Trang chủ Help Center:
    - Hiển thị FAQ công khai.
    - Tìm kiếm FAQ.
    - Lọc FAQ theo danh mục.
    - Cá nhân hóa gợi ý FAQ theo lịch sử xem.
    - Gợi ý FAQ phổ biến nếu chưa có lịch sử.
    """
    keyword = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()

    categories = FAQCategory.objects.filter(
        dang_hien_thi=True
    )

    faqs = FAQArticle.objects.filter(
        dang_hien_thi=True,
        danh_muc__dang_hien_thi=True
    ).select_related("danh_muc")

    # Tìm kiếm theo câu hỏi hoặc câu trả lời.
    if keyword:
        faqs = faqs.filter(
            Q(cau_hoi__icontains=keyword)
            | Q(cau_tra_loi__icontains=keyword)
        )

    # Lọc theo danh mục.
    if category_id.isdigit():
        faqs = faqs.filter(
            danh_muc_id=int(category_id)
        )
    elif category_id:
        faqs = faqs.none()

    # Đếm lượt xem của từng FAQ.
    faq_pho_bien = FAQArticle.objects.filter(
        dang_hien_thi=True,
        danh_muc__dang_hien_thi=True
    ).annotate(
        so_luot_xem=Count("interactions")
    ).order_by(
        "-so_luot_xem",
        "-thoi_diem_tao"
    )

    # Cá nhân hóa theo lịch sử xem của khách hàng đăng nhập.
    if request.user.is_authenticated:

        # Tìm các danh mục khách hàng thường xem.
        danh_muc_quan_tam = FAQInteraction.objects.filter(
            khach_hang=request.user
        ).values(
            "faq__danh_muc_id"
        ).annotate(
            so_luot_quan_tam=Count("id")
        ).order_by(
            "-so_luot_quan_tam"
        )

        danh_sach_danh_muc = [
            item["faq__danh_muc_id"]
            for item in danh_muc_quan_tam
        ]

        if danh_sach_danh_muc:
            faq_goi_y = faq_pho_bien.filter(
                danh_muc_id__in=danh_sach_danh_muc
            )[:5]
            ten_goi_y = "Gợi ý dành cho bạn"
        else:
            faq_goi_y = faq_pho_bien[:5]
            ten_goi_y = "Câu hỏi được quan tâm"
    else:
        # Khách chưa đăng nhập: hiển thị FAQ phổ biến.
        faq_goi_y = faq_pho_bien[:5]
        ten_goi_y = "Câu hỏi được quan tâm"

    context = {
        "categories": categories,
        "faqs": faqs,
        "keyword": keyword,
        "selected_category": category_id,
        "faq_goi_y": faq_goi_y,
        "ten_goi_y": ten_goi_y,
    }

    return render(request, "support/home.html", context)


def faq_detail(request, faq_id):
    """
    Hiển thị chi tiết FAQ, ghi nhận lượt xem
    và gợi ý tối đa 3 FAQ cùng danh mục.
    """
    faq = get_object_or_404(
        FAQArticle.objects.select_related("danh_muc"),
        id=faq_id,
        dang_hien_thi=True,
        danh_muc__dang_hien_thi=True
    )

    khach_hang = (
        request.user
        if request.user.is_authenticated
        else None
    )

    FAQInteraction.objects.create(
        faq=faq,
        khach_hang=khach_hang
    )

    if request.user.is_authenticated:
        da_danh_gia = FAQFeedback.objects.filter(
            faq=faq,
            khach_hang=request.user
        ).exists()
    else:
        danh_sach_da_danh_gia = request.session.get(
            "faq_da_danh_gia",
            []
        )
        da_danh_gia = faq.id in danh_sach_da_danh_gia

    # Gợi ý tối đa 3 FAQ khác cùng danh mục.
    faq_lien_quan = FAQArticle.objects.filter(
        danh_muc=faq.danh_muc,
        dang_hien_thi=True,
        danh_muc__dang_hien_thi=True
    ).exclude(
        id=faq.id
    ).order_by(
        "-thoi_diem_tao",
        "-id"
    )[:3]

    return render(
        request,
        "support/faq_detail.html",
        {
            "faq": faq,
            "da_danh_gia": da_danh_gia,
            "faq_lien_quan": faq_lien_quan,
        }
    )


@require_POST
def faq_feedback(request, faq_id):
    """
    Nhận đánh giá FAQ qua POST.
    Hạn chế đánh giá trùng theo tài khoản hoặc Session.
    """
    faq = get_object_or_404(
        FAQArticle,
        id=faq_id,
        dang_hien_thi=True,
        danh_muc__dang_hien_thi=True
    )

    gia_tri = request.POST.get("huu_ich")

    if gia_tri not in ("true", "false"):
        return redirect("support:faq_detail", faq_id=faq.id)

    if request.user.is_authenticated:
        FAQFeedback.objects.get_or_create(
            faq=faq,
            khach_hang=request.user,
            defaults={
                "huu_ich": gia_tri == "true"
            }
        )
    else:
        danh_sach_da_danh_gia = request.session.get(
            "faq_da_danh_gia",
            []
        )

        if faq.id not in danh_sach_da_danh_gia:
            FAQFeedback.objects.create(
                faq=faq,
                khach_hang=None,
                huu_ich=(gia_tri == "true")
            )

            danh_sach_da_danh_gia.append(faq.id)
            request.session["faq_da_danh_gia"] = (
                danh_sach_da_danh_gia
            )

    return redirect("support:faq_detail", faq_id=faq.id)