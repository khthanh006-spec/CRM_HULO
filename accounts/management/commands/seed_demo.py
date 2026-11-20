
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Staff
from customers.models import Customer


DEMO_USERS = [
    # CSKH
    ("cskh01", "Nguyễn Văn An", "CSKH"),
    ("cskh02", "Lê Thị Ngọc Mai", "CSKH"),
    ("cskh03", "Phạm Quốc Huy", "CSKH"),
    ("cskh04", "Trần Thị Thu Hà", "CSKH"),
    ("cskh05", "Võ Minh Tuấn", "CSKH"),

    # THẨM ĐỊNH
    ("thamdinh01", "Trần Minh Bình", "ASSESSOR"),
    ("thamdinh02", "Nguyễn Hoàng Phúc", "ASSESSOR"),
    ("thamdinh03", "Đặng Thị Bảo Ngọc", "ASSESSOR"),
    ("thamdinh04", "Lê Đức Thành", "ASSESSOR"),
    ("thamdinh05", "Phan Thị Minh Anh", "ASSESSOR"),

    # QUẢN LÝ
    ("quanly01", "Lê Thanh Mai", "MANAGER"),

    # KHÁCH HÀNG
    ("khachhang01", "Nguyễn Thị Hoa", "CUSTOMER"),
    ("khachhang02", "Trần Minh Anh", "CUSTOMER"),
    ("khachhang03", "Lê Hoàng Phúc", "CUSTOMER"),
    ("khachhang04", "Phạm Ngọc Hân", "CUSTOMER"),
    ("khachhang05", "Võ Gia Bảo", "CUSTOMER"),
]


class Command(BaseCommand):
    help = "Tạo tài khoản và hồ sơ demo CRM HULO"

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        password = os.environ.get("HULO_DEMO_PASSWORD")

        if not password:
            raise CommandError(
                "Chưa cấu hình HULO_DEMO_PASSWORD."
            )

        created_count = 0
        existing_count = 0

        for username, name, role in DEMO_USERS:
            email = f"{username}@example.com"

            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email},
            )

            if created:
                user.set_password(password)
                user.save(update_fields=["password"])
                created_count += 1
            else:
                existing_count += 1

            if role == "CUSTOMER":
                if Staff.objects.filter(
                    ma_tai_khoan=user
                ).exists():
                    raise CommandError(
                        f"{username} đã có hồ sơ nhân viên."
                    )

                Customer.objects.get_or_create(
                    ma_tai_khoan=user,
                    defaults={
                        "ho_ten": name,
                        "email": email,
                    },
                )

            else:
                if Customer.objects.filter(
                    ma_tai_khoan=user
                ).exists():
                    raise CommandError(
                        f"{username} đã có hồ sơ khách hàng."
                    )

                staff, _ = Staff.objects.get_or_create(
                    ma_tai_khoan=user,
                    defaults={
                        "ho_ten": name,
                        "email": email,
                        "vai_tro": role,
                        "san_sang_nhan_viec": True,
                        "quyen_quan_ly_noi_dung": False,
                    },
                )

                if staff.vai_tro != role:
                    raise CommandError(
                        f"{username}: sai vai trò hiện tại."
                    )

            self.stdout.write(
                f"[OK] {username} | {role}"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Tạo mới: {created_count} | "
                f"Đã tồn tại: {existing_count}"
            )
        )
