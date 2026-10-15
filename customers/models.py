
from django.db import models
from django.conf import settings


class Customer(models.Model):

    ma_khach_hang = models.AutoField(
        primary_key=True
    )

    ma_tai_khoan = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='customer_profile'
    )

    ho_ten = models.CharField(
        max_length=150
    )

    email = models.EmailField(
        unique=True
    )

    so_dien_thoai = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    dia_chi_mac_dinh = models.TextField(
        blank=True,
        null=True
    )

    thoi_diem_tao = models.DateTimeField(
        auto_now_add=True
    )

    thoi_diem_cap_nhat = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.ma_khach_hang} - {self.ho_ten}"

