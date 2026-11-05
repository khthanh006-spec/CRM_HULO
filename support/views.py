
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q, Case, When, Value, IntegerField, Count
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import (
    FAQCategory,
    FAQArticle,
    FAQInteraction,
    FAQFeedback,
)


def support_home(request):
    """
    Trang Help Center tích hợp M1 FAQ và M2 Chatbot.
    """

    keyword = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    faq_id = request.GET.get("faq", "").strip()

    # 1. Danh mục FAQ
    categories = FAQCategory.objects.filter(
        dang_hien_thi=True
    ).annotate(
        thu_tu_hien_thi=Case(
            When(ten_danh_muc="Đơn hàng", then=Value(1)),
            When(ten_danh_muc="Giao hàng", then=Value(2)),
            When(ten_danh_muc="Đổi trả", then=Value(3)),
            When(ten_danh_muc="Thanh toán", then=Value(4)),
            default=Value(99),
            output_field=IntegerField(),
        )
    ).order_by("thu_tu_hien_thi", "id")

    # 2. FAQ đang hiển thị
    faq_co_so = FAQArticle.objects.filter(
        dang_hien_thi=True,
        danh_muc__dang_hien_thi=True
    ).select_related("danh_muc")

    # 3. FAQ phổ biến
    faq_pho_bien = faq_co_so.annotate(
        so_luot_xem=Count("interactions")
    ).order_by(
        "-so_luot_xem",
        "-thoi_diem_tao",
        "-id"
    )[:4]

    # 4. FAQ gợi ý cá nhân hóa
    ten_goi_y = "Câu hỏi được quan tâm"
    faq_goi_y = faq_pho_bien

    if request.user.is_authenticated:
        faq_da_xem_ids = FAQInteraction.objects.filter(
            khach_hang=request.user
        ).values_list("faq_id", flat=True)

        if faq_da_xem_ids.exists():
            ten_goi_y = "Gợi ý dành cho bạn"

            faq_goi_y = faq_co_so.filter(
                id__in=faq_da_xem_ids
            ).annotate(
                so_luot_xem=Count("interactions")
            ).order_by(
                "-so_luot_xem",
                "-thoi_diem_tao",
                "-id"
            )[:4]

            if not faq_goi_y.exists():
                ten_goi_y = "Câu hỏi được quan tâm"
                faq_goi_y = faq_pho_bien

    # 5. Lọc FAQ theo danh mục
    faq_queryset = faq_co_so

    if category_id.isdigit():
        faq_queryset = faq_queryset.filter(
            danh_muc_id=int(category_id)
        )
    elif category_id:
        faq_queryset = faq_queryset.none()

    # 6. Tìm kiếm FAQ
    if keyword:
        faq_queryset = faq_queryset.filter(
            Q(cau_hoi__icontains=keyword)
            | Q(cau_tra_loi__icontains=keyword)
        )

    faq_queryset = faq_queryset.order_by(
        "-thoi_diem_tao",
        "-id"
    )

    # 7. FAQ được khách hàng lựa chọn
    selected_faq = None

    if faq_id.isdigit():
        selected_faq = faq_queryset.filter(
            id=int(faq_id)
        ).first()

        if selected_faq is not None:
            FAQInteraction.objects.create(
                faq=selected_faq,
                khach_hang=(
                    request.user
                    if request.user.is_authenticated
                    else None
                )
            )

    # 8. Hiển thị tối đa 4 FAQ
    faqs = faq_queryset[:4]

    # 9. Lịch sử Chatbot M2
    tin_nhan = []

    if request.user.is_authenticated:
        from customers.models import Customer
        from chatbot.models import ChatSession

        khach_hang = Customer.objects.filter(
            ma_tai_khoan=request.user
        ).first()

        if khach_hang is not None:
            phien_chat = ChatSession.objects.filter(
                ma_khach_hang=khach_hang,
                trang_thai="DANG_CHAT"
            ).order_by(
                "-ma_phien"
            ).first()

            if phien_chat is None:
                phien_chat = ChatSession.objects.filter(
                    ma_khach_hang=khach_hang
                ).order_by(
                    "-ma_phien"
                ).first()

            if phien_chat is not None:
                tin_nhan = phien_chat.messages.all().order_by(
                    "thoi_diem_gui",
                    "ma_tin_nhan"
                )

    # 10. Truyền dữ liệu sang template
    context = {
        "categories": categories,
        "faqs": faqs,
        "faq_goi_y": faq_goi_y,
        "ten_goi_y": ten_goi_y,
        "keyword": keyword,
        "selected_category": category_id,
        "selected_faq": selected_faq,
        "tin_nhan": tin_nhan,
    }

    return render(
        request,
        "support/home.html",
        context
    )


def faq_detail(request, faq_id):
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

        da_danh_gia = (
            str(faq.id) in [
                str(x) for x in danh_sach_da_danh_gia
            ]
        )

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
    faq = get_object_or_404(
        FAQArticle.objects.select_related("danh_muc"),
        id=faq_id,
        dang_hien_thi=True,
        danh_muc__dang_hien_thi=True
    )

    gia_tri = request.POST.get("huu_ich")

    if gia_tri not in ("true", "false"):
        messages.error(
            request,
            "Đánh giá không hợp lệ. Vui lòng thử lại."
        )
    else:
        gia_tri_bool = gia_tri == "true"

        if request.user.is_authenticated:
            FAQFeedback.objects.update_or_create(
                faq=faq,
                khach_hang=request.user,
                defaults={
                    "huu_ich": gia_tri_bool
                }
            )
        else:
            feedback_ids = request.session.get(
                "faq_feedback_ids",
                {}
            )

            feedback_id = feedback_ids.get(str(faq.id))

            feedback = None

            if feedback_id:
                feedback = FAQFeedback.objects.filter(
                    pk=feedback_id,
                    faq=faq,
                    khach_hang__isnull=True
                ).first()

            if feedback is not None:
                feedback.huu_ich = gia_tri_bool
                feedback.save(update_fields=["huu_ich"])
            else:
                feedback = FAQFeedback.objects.create(
                    faq=faq,
                    khach_hang=None,
                    huu_ich=gia_tri_bool
                )

                feedback_ids[str(faq.id)] = feedback.pk
                request.session["faq_feedback_ids"] = feedback_ids

            danh_sach_da_danh_gia = request.session.get(
                "faq_da_danh_gia",
                []
            )

            if str(faq.id) not in [
                str(item) for item in danh_sach_da_danh_gia
            ]:
                danh_sach_da_danh_gia.append(faq.id)

            request.session["faq_da_danh_gia"] = danh_sach_da_danh_gia

        if gia_tri_bool:
            messages.success(
                request,
                "Cảm ơn bạn đã đánh giá. "
                "Chúng tôi rất vui vì thông tin này "
                "đã giúp ích cho bạn!"
            )
        else:
            messages.warning(
                request,
                "Bạn vẫn chưa giải quyết được vấn đề? "
                "Hãy tiếp tục trò chuyện cùng HULO Assistant "
                "để được hỗ trợ chi tiết hơn nhé!"
            )

    category_id = request.POST.get(
        "category",
        str(faq.danh_muc_id)
    )

    keyword = request.POST.get("q", "").strip()

    parameters = {
        "category": category_id,
        "faq": faq.id,
    }

    if keyword:
        parameters["q"] = keyword

    url = (
        reverse("support:home")
        + "?"
        + urlencode(parameters)
    )

    return redirect(url)
