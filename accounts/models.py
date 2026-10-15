
from django.db import models
from django.conf import settings


class Staff(models.Model):

    ROLE_CHOICES = [
        ('CSKH', 'Nhân viên CSKH'),
        ('ASSESSOR', 'Nhân viên thẩm định'),
        ('MANAGER', 'Quản lý'),
    ]

    ma_nhan_vien = models.AutoField(primary_key=True)

    ma_tai_khoan = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='staff_profile'
    )

    ho_ten = models.CharField(max_length=150)

    email = models.EmailField()

    so_dien_thoai = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    vai_tro = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES
    )

    san_sang_nhan_viec = models.BooleanField(default=False)

    quyen_quan_ly_noi_dung = models.BooleanField(default=False)

    thoi_diem_tao = models.DateTimeField(auto_now_add=True)

    thoi_diem_cap_nhat = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ho_ten} - {self.get_vai_tro_display()}"

