
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import (
    FAQCategory,
    FAQArticle,
    FAQFeedback,
    FAQInteraction,
)


class HelpCenterTests(TestCase):

    def setUp(self):
        self.category = FAQCategory.objects.create(
            ten_danh_muc="Đơn hàng",
            mo_ta="Các câu hỏi về đơn hàng",
            dang_hien_thi=True
        )

        self.faq = FAQArticle.objects.create(
            danh_muc=self.category,
            cau_hoi="Làm thế nào để kiểm tra đơn hàng?",
            cau_tra_loi="Bạn có thể kiểm tra trong mục đơn hàng.",
            dang_hien_thi=True
        )

    # UC01.01 - Hiển thị Help Center
    def test_help_center_loads(self):
        response = self.client.get(reverse("support:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Làm thế nào để kiểm tra đơn hàng?"
        )

    # UC01.02 - Tìm kiếm FAQ
    def test_search_faq(self):
        response = self.client.get(
            reverse("support:home"),
            {"q": "kiểm tra đơn hàng"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Làm thế nào để kiểm tra đơn hàng?"
        )

    # UC01.02 - Lọc FAQ theo danh mục
    def test_filter_faq_by_category(self):
        response = self.client.get(
            reverse("support:home"),
            {"category": str(self.category.id)}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Làm thế nào để kiểm tra đơn hàng?"
        )

    # UC01.07 - Khách chưa đăng nhập nhận FAQ phổ biến
    def test_anonymous_user_sees_popular_faq_fallback(self):
        response = self.client.get(reverse("support:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["ten_goi_y"],
            "Câu hỏi được quan tâm"
        )
        self.assertIn(
            self.faq,
            response.context["faq_goi_y"]
        )

    # UC01.07 - Khách đăng nhập nhưng chưa có lịch sử
    def test_authenticated_user_without_history_sees_fallback(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="test_no_history",
            password="testpassword123"
        )

        self.client.force_login(user)

        response = self.client.get(reverse("support:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["ten_goi_y"],
            "Câu hỏi được quan tâm"
        )

    # UC01.07 - Khách có lịch sử được gợi ý cá nhân hóa
    def test_authenticated_user_gets_personalized_faq(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="test_with_history",
            password="testpassword123"
        )

        FAQInteraction.objects.create(
            faq=self.faq,
            khach_hang=user
        )

        self.client.force_login(user)

        response = self.client.get(reverse("support:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["ten_goi_y"],
            "Gợi ý dành cho bạn"
        )
        self.assertIn(
            self.faq,
            response.context["faq_goi_y"]
        )

    # UC01.07 - Truy cập FAQ ghi nhận lịch sử tương tác
    def test_faq_detail_creates_interaction(self):
        response = self.client.get(
            reverse(
                "support:faq_detail",
                args=[self.faq.id]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            FAQInteraction.objects.filter(
                faq=self.faq
            ).count(),
            1
        )

    # UC01.03 - Gửi đánh giá hữu ích
    def test_feedback_positive(self):
        response = self.client.post(
            reverse(
                "support:faq_feedback",
                args=[self.faq.id]
            ),
            {"huu_ich": "true"}
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            FAQFeedback.objects.filter(
                faq=self.faq,
                huu_ich=True
            ).exists()
        )

    # UC01.03 - Khách ẩn danh không đánh giá trùng
    def test_anonymous_user_cannot_submit_feedback_twice(self):
        feedback_url = reverse(
            "support:faq_feedback",
            args=[self.faq.id]
        )

        self.client.post(
            feedback_url,
            {"huu_ich": "true"}
        )

        self.client.post(
            feedback_url,
            {"huu_ich": "false"}
        )

        self.assertEqual(
            FAQFeedback.objects.filter(faq=self.faq).count(),
            1
        )

    # Kiểm tra FAQ ẩn không xuất hiện trên trang chủ
    def test_hidden_faq_does_not_appear_on_homepage(self):
        self.faq.dang_hien_thi = False
        self.faq.save()

        response = self.client.get(reverse("support:home"))

        self.assertNotContains(
            response,
            "Làm thế nào để kiểm tra đơn hàng?"
        )

    # Kiểm tra không truy cập được FAQ đã ẩn
    def test_hidden_faq_cannot_be_opened(self):
        self.faq.dang_hien_thi = False
        self.faq.save()

        response = self.client.get(
            reverse(
                "support:faq_detail",
                args=[self.faq.id]
            )
        )

        self.assertEqual(response.status_code, 404)

    # Kiểm tra không truy cập FAQ thuộc danh mục đã ẩn
    def test_hidden_category_faq_cannot_be_opened(self):
        self.category.dang_hien_thi = False
        self.category.save()

        response = self.client.get(
            reverse(
                "support:faq_detail",
                args=[self.faq.id]
            )
        )

        self.assertEqual(response.status_code, 404)

    # Kiểm tra dữ liệu đánh giá không hợp lệ
    def test_invalid_feedback_is_not_saved(self):
        response = self.client.post(
            reverse(
                "support:faq_feedback",
                args=[self.faq.id]
            ),
            {"huu_ich": "invalid"}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            FAQFeedback.objects.filter(faq=self.faq).count(),
            0
        )
