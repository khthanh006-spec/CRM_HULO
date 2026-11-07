
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

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

        # ==================================================
        # DANH SÁCH TÀI KHOẢN MẪU
        # ==================================================

        demo_users = [
            # NHÂN VIÊN CHĂM SÓC KHÁCH HÀNG
            {
                "username": "cskh01",
                "name": "Nguyễn Văn An",
                "email": "cskh01@example.com",
                "role": "CSKH",
            },
            {
                "username": "cskh02",
                "name": "Lê Thị Ngọc Mai",
                "email": "cskh02@example.com",
                "role": "CSKH",
            },
            {
                "username": "cskh03",
                "name": "Phạm Quốc Huy",
                "email": "cskh03@example.com",
                "role": "CSKH",
            },
            {
                "username": "cskh04",
                "name": "Trần Thị Thu Hà",
                "email": "cskh04@example.com",
                "role": "CSKH",
            },
            {
                "username": "cskh05",
                "name": "Võ Minh Tuấn",
                "email": "cskh05@example.com",
                "role": "CSKH",
            },

            # NHÂN VIÊN THẨM ĐỊNH
            {
                "username": "thamdinh01",
                "name": "Trần Minh Bình",
                "email": "thamdinh01@example.com",
                "role": "ASSESSOR",
            },
            {
                "username": "thamdinh02",
                "name": "Nguyễn Hoàng Phúc",
                "email": "thamdinh02@example.com",
                "role": "ASSESSOR",
            },
            {
                "username": "thamdinh03",
                "name": "Đặng Thị Bảo Ngọc",
                "email": "thamdinh03@example.com",
                "role": "ASSESSOR",
            },
            {
                "username": "thamdinh04",
                "name": "Lê Đức Thành",
                "email": "thamdinh04@example.com",
                "role": "ASSESSOR",
            },
            {
                "username": "thamdinh05",
                "name": "Phan Thị Minh Anh",
                "email": "thamdinh05@example.com",
                "role": "ASSESSOR",
            },

            # QUẢN LÝ
            {
                "username": "quanly01",
                "name": "Lê Thanh Mai",
                "email": "quanly01@example.com",
                "role": "MANAGER",
            },

            # KHÁCH HÀNG MẪU BAN ĐẦU
            {
                "username": "khachhang01",
                "name": "Nguyễn Thị Hoa",
                "email": "khachhang01@example.com",
                "role": "CUSTOMER",
            },
        ]

        created_count = 0
        existing_count = 0

        # ==================================================
        # TẠO USER VÀ HỒ SƠ STAFF / CUSTOMER
        # ==================================================

        for data in demo_users:
            username = data["username"]

            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": data["email"],
                    },
                )

                # Chỉ tạo mật khẩu cho tài khoản mới.
                # Không thay đổi mật khẩu đã có.
                if created:
                    user.set_password(password)
                    user.save(update_fields=["password"])

                if data["role"] == "CUSTOMER":
                    if Staff.objects.filter(
                        ma_tai_khoan=user
                    ).exists():
                        raise CommandError(
                            f"{username} đã có hồ sơ nhân viên."
                        )

                    Customer.objects.get_or_create(
                        ma_tai_khoan=user,
                        defaults={
                            "ho_ten": data["name"],
                            "email": data["email"],
                        },
                    )

                else:
                    if Customer.objects.filter(
                        ma_tai_khoan=user
                    ).exists():
                        raise CommandError(
                            f"{username} đã có hồ sơ khách hàng."
                        )

                    staff, staff_created = (
                        Staff.objects.get_or_create(
                            ma_tai_khoan=user,
                            defaults={
                                "ho_ten": data["name"],
                                "email": data["email"],
                                "vai_tro": data["role"],
                                "san_sang_nhan_viec": True,
                                "quyen_quan_ly_noi_dung": False,
                            },
                        )
                    )

                    # Kiểm tra vai trò tài khoản có sẵn.
                    # Không tự ý thay đổi quyền hiện tại.
                    if staff.vai_tro != data["role"]:
                        raise CommandError(
                            f"{username} đang có vai trò "
                            f"{staff.vai_tro}, không khớp "
                            f"vai trò mong đợi {data['role']}."
                        )

                if created:
                    created_count += 1
                    status = "Tạo mới"
                else:
                    existing_count += 1
                    status = "Đã tồn tại"

                self.stdout.write(
                    f"{status}: {username} "
                    f"({data['role']})"
                )

        # ==================================================
        # THỐNG KÊ KẾT QUẢ
        # ==================================================

        so_cskh = Staff.objects.filter(
            vai_tro="CSKH"
        ).count()

        so_tham_dinh = Staff.objects.filter(
            vai_tro="ASSESSOR"
        ).count()

        so_quan_ly = Staff.objects.filter(
            vai_tro="MANAGER"
        ).count()

        self.stdout.write("")
        self.stdout.write("========== KẾT QUẢ ==========")
        self.stdout.write(
            f"Tài khoản tạo mới: {created_count}"
        )
        self.stdout.write(
            f"Tài khoản đã tồn tại: {existing_count}"
        )
        self.stdout.write(
            f"Nhân viên CSKH: {so_cskh}"
        )
        self.stdout.write(
            f"Nhân viên thẩm định: {so_tham_dinh}"
        )
        self.stdout.write(
            f"Nhân viên quản lý: {so_quan_ly}"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Hoàn tất tạo dữ liệu mẫu CRM HULO!"
            )
        )
