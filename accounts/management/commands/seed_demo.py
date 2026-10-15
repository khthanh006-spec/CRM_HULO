
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Staff
from customers.models import Customer


class Command(BaseCommand):
    help = "Tạo tài khoản và hồ sơ mẫu cho CRM HULO"

    def handle(self, *args, **options):
        User = get_user_model()

        password = os.environ.get("HULO_DEMO_PASSWORD")

        if not password:
            raise CommandError(
                "Chưa cấu hình HULO_DEMO_PASSWORD. "
                "Hãy đặt mật khẩu thử nghiệm trước khi chạy."
            )

        # Tài khoản mẫu của nhóm
        demo_users = [
            {
                "username": "cskh01",
                "name": "Nguyễn Văn An",
                "email": "cskh01@example.com",
                "role": "CSKH",
            },
            {
                "username": "thamdinh01",
                "name": "Trần Minh Bình",
                "email": "thamdinh01@example.com",
                "role": "ASSESSOR",
            },
            {
                "username": "quanly01",
                "name": "Lê Thanh Mai",
                "email": "quanly01@example.com",
                "role": "MANAGER",
            },
            {
                "username": "khachhang01",
                "name": "Nguyễn Thị Hoa",
                "email": "khachhang01@example.com",
                "role": "CUSTOMER",
            },
        ]

        for data in demo_users:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={
                    "email": data["email"],
                }
            )

            # Chỉ đặt mật khẩu khi tạo tài khoản mới.
            # Không ghi đè mật khẩu tài khoản đã tồn tại.
            if created:
                user.set_password(password)
                user.save()

            if data["role"] == "CUSTOMER":
                # Tránh một tài khoản có cả hồ sơ Staff và Customer
                if Staff.objects.filter(ma_tai_khoan=user).exists():
                    raise CommandError(
                        f"{user.username} đã có hồ sơ nhân viên."
                    )

                Customer.objects.get_or_create(
                    ma_tai_khoan=user,
                    defaults={
                        "ho_ten": data["name"],
                        "email": data["email"],
                    }
                )
            else:
                if Customer.objects.filter(ma_tai_khoan=user).exists():
                    raise CommandError(
                        f"{user.username} đã có hồ sơ khách hàng."
                    )

                Staff.objects.get_or_create(
                    ma_tai_khoan=user,
                    defaults={
                        "ho_ten": data["name"],
                        "email": data["email"],
                        "vai_tro": data["role"],
                        "san_sang_nhan_viec": True,
                    }
                )

            status = "Tạo mới" if created else "Đã tồn tại"
            self.stdout.write(
                f"{status}: {data['username']}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Hoàn tất tạo dữ liệu mẫu CRM HULO!"
            )
        )
