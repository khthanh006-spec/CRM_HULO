from django.test import TestCase
from django.urls import reverse

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

    def test_help_center_loads(self):
        response = self.client.get(reverse("support:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Làm thế nào để kiểm tra đơn hàng?"
        )

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