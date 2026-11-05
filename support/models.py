
from django.conf import settings
from django.db import models


class FAQCategory(models.Model):
    ten_danh_muc = models.CharField(max_length=150, unique=True)
    mo_ta = models.TextField(blank=True)
    dang_hien_thi = models.BooleanField(default=True)
    thoi_diem_tao = models.DateTimeField(auto_now_add=True)
    thoi_diem_cap_nhat = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ten_danh_muc"]
        verbose_name = "Danh mục FAQ"
        verbose_name_plural = "Danh mục FAQ"

    def __str__(self):
        return self.ten_danh_muc


class FAQArticle(models.Model):
    danh_muc = models.ForeignKey(
        FAQCategory,
        on_delete=models.PROTECT,
        related_name="faq_articles"
    )
    cau_hoi = models.CharField(max_length=255)
    cau_tra_loi = models.TextField()
    dang_hien_thi = models.BooleanField(default=True)
    thoi_diem_tao = models.DateTimeField(auto_now_add=True)
    thoi_diem_cap_nhat = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-thoi_diem_cap_nhat"]
        verbose_name = "Bài viết FAQ"
        verbose_name_plural = "Bài viết FAQ"

    def __str__(self):
        return self.cau_hoi


class FAQFeedback(models.Model):
    faq = models.ForeignKey(
        FAQArticle,
        on_delete=models.CASCADE,
        related_name="feedbacks"
    )
    khach_hang = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faq_feedbacks"
    )
    huu_ich = models.BooleanField()
    thoi_diem_danh_gia = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-thoi_diem_danh_gia"]
        verbose_name = "Đánh giá FAQ"
        verbose_name_plural = "Đánh giá FAQ"

    def __str__(self):
        ket_qua = "Hữu ích" if self.huu_ich else "Không hữu ích"
        return f"{self.faq_id} - {ket_qua}"


class FAQInteraction(models.Model):
    faq = models.ForeignKey(
        FAQArticle,
        on_delete=models.CASCADE,
        related_name="interactions"
    )
    khach_hang = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faq_interactions"
    )
    thoi_diem_xem = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-thoi_diem_xem"]
        verbose_name = "Lượt xem FAQ"
        verbose_name_plural = "Lượt xem FAQ"

    def __str__(self):
        return f"FAQ {self.faq_id} - {self.thoi_diem_xem}"
