
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.crypto import get_random_string

from customers.models import Customer


User = get_user_model()


DEMO_CUSTOMERS = [
    {
        "username": "khachhang02",
        "full_name": "Trần Minh Anh",
        "email": "khachhang02@example.com",
        "phone": "0900000002",
    },
    {
        "username": "khachhang03",
        "full_name": "Lê Hoàng Phúc",
        "email": "khachhang03@example.com",
        "phone": "0900000003",
    },
    {
        "username": "khachhang04",
        "full_name": "Phạm Ngọc Hân",
        "email": "khachhang04@example.com",
        "phone": "0900000004",
    },
    {
        "username": "khachhang05",
        "full_name": "Võ Gia Bảo",
        "email": "khachhang05@example.com",
        "phone": "0900000005",
    },
]


print("=" * 65)
print("TAO TAI KHOAN KHACH HANG DEMO - CRM HULO")
print("=" * 65)

created_count = 0

for data in DEMO_CUSTOMERS:
    username = data["username"]

    with transaction.atomic():
        user = User.objects.filter(
            username=username
        ).first()

        if user is None:
            password = get_random_string(16)

            user = User.objects.create_user(
                username=username,
                email=data["email"],
                password=password,
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )

            user.groups.clear()
            user.user_permissions.clear()

            print(f"\n[TAO MOI] {username}")
            print(f"Mat khau: {password}")

            created_count += 1

        else:
            print(f"\n[DA TON TAI] {username}")
            print("Giu nguyen mat khau hien tai.")

        customer, customer_created = (
            Customer.objects.get_or_create(
                ma_tai_khoan=user,
                defaults={
                    "ho_ten": data["full_name"],
                    "email": data["email"],
                    "so_dien_thoai": data["phone"],
                    "dia_chi_mac_dinh": (
                        "Địa chỉ giả lập - phục vụ demo CRM HULO"
                    ),
                },
            )
        )

        if customer_created:
            print("Da tao ho so Customer.")
        else:
            print("Ho so Customer da ton tai.")

        print(
            f"Customer ID: {customer.ma_khach_hang}"
        )
        print(
            f"Ho ten: {customer.ho_ten}"
        )


print("\n" + "=" * 65)
print(f"SO TAI KHOAN MOI: {created_count}")
print("HOAN THANH TAO DU LIEU KHACH HANG DEMO")
print("=" * 65)
