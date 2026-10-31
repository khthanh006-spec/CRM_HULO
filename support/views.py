
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import (
    Q,
    Case,
    When,
    Value,
    IntegerField,
)
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import (
    FAQCategory,
    FAQArticle,
    FAQInteraction,
    FAQFeedback,
)


# ======================================================
# 1. TRANG CHU TRUNG TAM HO TRO
# ======================================================

def support_home(request):
    """
    Trang Help Center tích hợp M1 FAQ và M2 Chatbot.

    - Hiển thị 4 danh mục hỗ trợ.
    - Chọn danh mục để xem tối đa 4 FAQ liên quan.
    - Tìm kiếm FAQ theo câu hỏi và câu trả lời.
    - Chọn FAQ để xem câu trả lời.
    - Ghi nhận lượt xem FAQ.
    - Hiển thị lịch sử Chatbot M2.
    """

    keyword = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    faq_id = request.GET.get("faq", "").strip()

    # ==================================================
    # 2. DANH MUC FAQ
    # ==================================================

    categories = FAQCategory.objects.filter(
        dang_hien_thi=True
    ).annotate(
        thu_tu_hien_thi=Case(
            When(
                ten_danh_muc="Đơn hàng",
                then=Value(1)
            ),
            When(
                ten_danh_muc="Giao hàng",
                then=Value(2)
            ),
            When(
                ten_danh_muc="Đổi trả",
                then=Value(3)
            ),
            When(
                ten_danh_muc="Thanh toán",
                then=Value(4)
            ),
            default=Value(99),
            output_field=IntegerField(),
        )
    ).order_by(
        "thu_tu_hien_thi",
        "id"
    )

    # ==================================================
    # 3. LAY FAQ DANG HIEN THI
    # ==================================================

    faq_co_so = FAQArticle.objects.filter(
        dang_hien_thi=True,
        danh_muc__dang_hien_thi=True
    ).select_related(
        "danh_muc"
    )

    faq_queryset = faq_co_so

    # ==================================================
    # 4. LOC FAQ THEO DANH MUC
    # ==================================================

    if category_id.isdigit():

        faq_queryset = faq_queryset.filter(
            danh_muc_id=int(category_id)
        )

    elif category_id:

        faq_queryset = faq_queryset.none()

    # ==================================================
    # 5. TIM KIEM FAQ
    # ==================================================

    if keyword:

        faq_queryset = faq_queryset.filter(
            Q(cau_hoi__icontains=keyword)
            | Q(cau_tra_loi__icontains=keyword)
        )

    faq_queryset = faq_queryset.order_by(
        "-thoi_diem_tao",
        "-id"
    )

    # ==================================================
    # 6. FAQ DUOC KHACH HANG LUA CHON
    # QUAN TRONG: TIM TRUOC KHI CAT 4 FAQ
    # ==================================================

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

    # ==================================================
    # 7. GIOI HAN 4 FAQ
    # KHONG FILTER SAU KHI DA SLICE
    # ==================================================

    if category_id.isdigit() or keyword:

        faqs = faq_queryset[:4]

    else:

        faqs = faq_queryset.none()

    # ==================================================
    # 8. LAY LICH SU CHATBOT M2
    # ==================================================

    tin_nhan = []

    if request.user.is_authenticated:

        from customers.models import Customer
        from chatbot.models import ChatSession

        khach_hang = Customer.objects.filter(
            ma_tai_khoan=request.user
        ).first()

        if khach_hang is not None:

            # Tim phien dang tro chuyen gan nhat.
            # ChatSession su dung ma_phien lam khoa chinh.

            phien_chat = ChatSession.objects.filter(
                ma_khach_hang=khach_hang,
                trang_thai="DANG_CHAT"
            ).order_by(
                "-ma_phien"
            ).first()

            # Neu khong co phien dang tro chuyen,
            # lay phien gan nhat de hien thi lich su.

            if phien_chat is None:

                phien_chat = ChatSession.objects.filter(
                    ma_khach_hang=khach_hang
                ).order_by(
                    "-ma_phien"
                ).first()

            # Lay tin nhan theo thu tu gui.

            if phien_chat is not None:

                tin_nhan = phien_chat.messages.all().order_by(
                    "thoi_diem_gui",
                    "ma_tin_nhan"
                )

    # ==================================================
    # 9. TRUYEN DU LIEU SANG TEMPLATE
    # ==================================================

    context = {
        "categories": categories,
        "faqs": faqs,
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


# ======================================================
# 10. CHI TIET FAQ
# GIU LAI URL CU DE KHONG ANH HUONG LIEN KET
# ======================================================

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
            str(faq.id) in [str(x) for x in danh_sach_da_danh_gia]
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


# ======================================================
# 11. DANH GIA FAQ
# ======================================================

@require_POST
def faq_feedback(request, faq_id):

    faq = get_object_or_404(
        FAQArticle.objects.select_related("danh_muc"),
        id=faq_id,
        dang_hien_thi=True,
        danh_muc__dang_hien_thi=True
    )

    gia_tri = request.POST.get("huu_ich")

    # ==================================================
    # 12. KIEM TRA GIA TRI DANH GIA
    # ==================================================

    if gia_tri not in ("true", "false"):

        messages.error(
            request,
            "Đánh giá không hợp lệ. Vui lòng thử lại."
        )

    else:

        gia_tri_bool = gia_tri == "true"

        # ==============================================
        # KHACH HANG DA DANG NHAP
        # ==============================================

        if request.user.is_authenticated:

            feedback, da_tao_moi = FAQFeedback.objects.get_or_create(
                faq=faq,
                khach_hang=request.user,
                defaults={
                    "huu_ich": gia_tri_bool
                }
            )

            # Danh gia lan dau.

            if da_tao_moi:

                if feedback.huu_ich:

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

            # Da danh gia truoc do.
            # Khong ghi de ket qua cu.

            else:

                if feedback.huu_ich:

                    messages.success(
                        request,
                        "Bạn đã đánh giá câu hỏi này trước đó. "
                        "Đánh giá hữu ích trước đó vẫn được giữ nguyên."
                    )

                else:

                    messages.warning(
                        request,
                        "Bạn đã đánh giá câu hỏi này trước đó. "
                        "Đánh giá không hữu ích trước đó vẫn được giữ nguyên."
                    )

        # ==============================================
        # KHACH VANG LAI
        # ==============================================

        else:

            danh_sach_da_danh_gia = request.session.get(
                "faq_da_danh_gia",
                []
            )

            # Ho tro ca danh sach ID dang so va dang chuoi.

            danh_sach_id = [
                str(item)
                for item in danh_sach_da_danh_gia
            ]

            if str(faq.id) not in danh_sach_id:

                FAQFeedback.objects.create(
                    faq=faq,
                    khach_hang=None,
                    huu_ich=gia_tri_bool
                )

                danh_sach_da_danh_gia.append(faq.id)

                request.session["faq_da_danh_gia"] = (
                    danh_sach_da_danh_gia
                )

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

            else:

                messages.info(
                    request,
                    "Bạn đã đánh giá câu hỏi này trước đó. "
                    "Đánh giá cũ vẫn được giữ nguyên."
                )

    # ==================================================
    # 13. QUAY LAI FAQ VUA DANH GIA
    # GIU NGUYEN DANH MUC VA TU KHOA TIM KIEM
    # ==================================================

    category_id = request.POST.get(
        "category",
        str(faq.danh_muc_id)
    )

    keyword = request.POST.get(
        "q",
        ""
    ).strip()

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
