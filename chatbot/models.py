
from django.db import models


# 1. Quy tắc trả lời của Chatbot
class ChatRule(models.Model):
    ma_quy_tac = models.AutoField(primary_key=True)

    ten_chu_de = models.CharField(max_length=100)

    tu_khoa = models.CharField(max_length=255)

    cau_tra_loi = models.TextField(
        blank=True,
        null=True
    )

    thu_tu_uu_tien = models.PositiveIntegerField(default=0)

    dang_hoat_dong = models.BooleanField(default=True)

    thoi_diem_tao = models.DateTimeField(auto_now_add=True)
    thoi_diem_cap_nhat = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.ten_chu_de


# 2. Phiên trò chuyện giữa khách hàng và Chatbot
class ChatSession(models.Model):
    TRANG_THAI = [
        ('DANG_CHAT', 'Đang trò chuyện'),
        ('DA_KET_THUC', 'Đã kết thúc'),
    ]

    KET_QUA = [
        ('DA_GIAI_DAP', 'Đã giải đáp'),
        ('CAN_HO_TRO', 'Cần nhân viên hỗ trợ'),
        ('CHUA_XAC_DINH', 'Chưa xác định'),
    ]

    ma_phien = models.AutoField(primary_key=True)

    ma_khach_hang = models.ForeignKey(
        'customers.Customer',
        on_delete=models.PROTECT,
        related_name='chat_sessions'
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI,
        default='DANG_CHAT'
    )

    ket_qua = models.CharField(
        max_length=30,
        choices=KET_QUA,
        blank=True,
        null=True
    )

    thoi_diem_bat_dau = models.DateTimeField(auto_now_add=True)

    thoi_diem_ket_thuc = models.DateTimeField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"Phiên {self.ma_phien}"


# 3. Tin nhắn trong phiên Chatbot
class ChatMessage(models.Model):
    BEN_GUI = [
        ('KHACH_HANG', 'Khách hàng'),
        ('CHATBOT', 'Chatbot'),
    ]

    ma_tin_nhan = models.AutoField(primary_key=True)

    ma_phien = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages'
    )

    ben_gui = models.CharField(
        max_length=20,
        choices=BEN_GUI
    )

    noi_dung = models.TextField()

    ma_quy_tac = models.ForeignKey(
        ChatRule,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='messages'
    )

    thoi_diem_gui = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ben_gui} - {self.ma_tin_nhan}"
from django.db import models

# Create your models here.
