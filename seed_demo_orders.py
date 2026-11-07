
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from customers.models import Customer
from disputes.models import Order, OrderItem, Product


# ==========================================================
# CRM HULO - DU LIEU DEMO E2E MODULE 1 DEN MODULE 5
# 5 KHACH HANG - 15 DON HANG - 5 SAN PHAM
# ==========================================================

User = get_user_model()


# ----------------------------------------------------------
# 1. SAN PHAM DEMO
# ----------------------------------------------------------

PRODUCTS = {
    "HULO-DEMO-SP01": "Tai nghe Bluetooth HULO",
    "HULO-DEMO-SP02": "Sac du phong 10000mAh",
    "HULO-DEMO-SP03": "Binh giu nhiet inox 500ml",
    "HULO-DEMO-SP04": "Den ban LED chong can",
    "HULO-DEMO-SP05": "Balo laptop chong nuoc",
}


# ----------------------------------------------------------
# 2. DON HANG DEMO
# Moi khach hang co 3 don hang.
#
# Moi item:
# (SKU, SO LUONG, GIA TRI DA THANH TOAN)
#
# Gia tri da thanh toan la tong tien cua dong hang.
# ----------------------------------------------------------

ORDERS = [
    # ======================================================
    # KH01 - GIAO HANG CHAM
    # ======================================================
    {
        "username": "khachhang01",
        "code": "HULO-DEMO-001",
        "status": "DANG_GIAO",
        "scenario": "E2E-01 - Giao hang cham",
        "items": [
            ("HULO-DEMO-SP01", 1, "350000"),
            ("HULO-DEMO-SP03", 1, "180000"),
        ],
    },
    {
        "username": "khachhang01",
        "code": "HULO-DEMO-002",
        "status": "DA_GIAO",
        "scenario": "Don hang thanh cong",
        "items": [
            ("HULO-DEMO-SP04", 1, "250000"),
            ("HULO-DEMO-SP05", 1, "450000"),
        ],
    },
    {
        "username": "khachhang01",
        "code": "HULO-DEMO-003",
        "status": "CHO_XU_LY",
        "scenario": "Don hang cho xu ly",
        "items": [
            ("HULO-DEMO-SP02", 1, "320000"),
            ("HULO-DEMO-SP03", 2, "360000"),
        ],
    },

    # ======================================================
    # KH02 - SAN PHAM LOI / REOPENED
    # ======================================================
    {
        "username": "khachhang02",
        "code": "HULO-DEMO-004",
        "status": "DA_GIAO",
        "scenario": "E2E-02 - San pham bi loi",
        "items": [
            ("HULO-DEMO-SP01", 1, "350000"),
            ("HULO-DEMO-SP02", 1, "320000"),
        ],
    },
    {
        "username": "khachhang02",
        "code": "HULO-DEMO-005",
        "status": "DANG_GIAO",
        "scenario": "Theo doi van chuyen",
        "items": [
            ("HULO-DEMO-SP05", 1, "450000"),
            ("HULO-DEMO-SP03", 1, "180000"),
        ],
    },
    {
        "username": "khachhang02",
        "code": "HULO-DEMO-006",
        "status": "DA_HUY",
        "scenario": "Don hang da huy",
        "items": [
            ("HULO-DEMO-SP04", 1, "250000"),
            ("HULO-DEMO-SP02", 1, "320000"),
        ],
    },

    # ======================================================
    # KH03 - GIAO SAI SAN PHAM / TRANH CHAP
    # ======================================================
    {
        "username": "khachhang03",
        "code": "HULO-DEMO-007",
        "status": "DA_GIAO",
        "scenario": "E2E-03 - Giao sai san pham",
        "items": [
            ("HULO-DEMO-SP05", 1, "450000"),
            ("HULO-DEMO-SP03", 1, "180000"),
        ],
    },
    {
        "username": "khachhang03",
        "code": "HULO-DEMO-008",
        "status": "DA_GIAO",
        "scenario": "Don hang thanh cong",
        "items": [
            ("HULO-DEMO-SP01", 1, "350000"),
            ("HULO-DEMO-SP04", 1, "250000"),
        ],
    },
    {
        "username": "khachhang03",
        "code": "HULO-DEMO-009",
        "status": "CHO_XU_LY",
        "scenario": "Yeu cau thay doi don",
        "items": [
            ("HULO-DEMO-SP02", 1, "320000"),
            ("HULO-DEMO-SP05", 1, "450000"),
        ],
    },

    # ======================================================
    # KH04 - HOAN TIEN / THIEU BANG CHUNG
    # ======================================================
    {
        "username": "khachhang04",
        "code": "HULO-DEMO-010",
        "status": "DA_GIAO",
        "scenario": "E2E-04 - Hoan tien thieu bang chung",
        "items": [
            ("HULO-DEMO-SP02", 1, "320000"),
            ("HULO-DEMO-SP01", 1, "350000"),
        ],
    },
    {
        "username": "khachhang04",
        "code": "HULO-DEMO-011",
        "status": "DANG_GIAO",
        "scenario": "Don hang dang van chuyen",
        "items": [
            ("HULO-DEMO-SP04", 1, "250000"),
            ("HULO-DEMO-SP03", 1, "180000"),
        ],
    },
    {
        "username": "khachhang04",
        "code": "HULO-DEMO-012",
        "status": "DA_HUY",
        "scenario": "Don hang da huy",
        "items": [
            ("HULO-DEMO-SP05", 1, "450000"),
            ("HULO-DEMO-SP02", 1, "320000"),
        ],
    },

    # ======================================================
    # KH05 - CSAT THAP / LOYALTY / VOUCHER
    # ======================================================
    {
        "username": "khachhang05",
        "code": "HULO-DEMO-013",
        "status": "DA_GIAO",
        "scenario": "E2E-05 - Khach hang khong hai long",
        "items": [
            ("HULO-DEMO-SP04", 1, "250000"),
            ("HULO-DEMO-SP01", 1, "350000"),
        ],
    },
    {
        "username": "khachhang05",
        "code": "HULO-DEMO-014",
        "status": "DA_GIAO",
        "scenario": "Lich su mua hang",
        "items": [
            ("HULO-DEMO-SP03", 2, "360000"),
            ("HULO-DEMO-SP05", 1, "450000"),
        ],
    },
    {
        "username": "khachhang05",
        "code": "HULO-DEMO-015",
        "status": "CHO_XU_LY",
        "scenario": "Don hang can ho tro",
        "items": [
            ("HULO-DEMO-SP02", 1, "320000"),
            ("HULO-DEMO-SP04", 1, "250000"),
        ],
    },
]


# ----------------------------------------------------------
# 3. KIEM TRA KHACH HANG
# ----------------------------------------------------------

def get_customer(username):
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        raise ValueError(
            f"Khong tim thay tai khoan: {username}"
        )

    if not user.is_active:
        raise ValueError(
            f"Tai khoan khong hoat dong: {username}"
        )

    try:
        return Customer.objects.get(ma_tai_khoan=user)
    except Customer.DoesNotExist:
        raise ValueError(
            f"Tai khoan {username} chua co ho so Customer."
        )


# ----------------------------------------------------------
# 4. TAO SAN PHAM
# ----------------------------------------------------------

def create_products():
    product_map = {}
    created_count = 0

    for sku, name in PRODUCTS.items():
        product, created = Product.objects.get_or_create(
            ma_sku=sku,
            defaults={
                "ten_san_pham": name,
            },
        )

        if product.ten_san_pham != name:
            raise ValueError(
                f"SKU {sku} da ton tai voi ten khac: "
                f"{product.ten_san_pham}"
            )

        product_map[sku] = product

        if created:
            created_count += 1

    return product_map, created_count


# ----------------------------------------------------------
# 5. TAO DON HANG VA CHI TIET DON
# ----------------------------------------------------------

def create_orders(product_map):
    created_orders = 0
    created_items = 0
    existing_orders = 0

    for data in ORDERS:
        customer = get_customer(data["username"])

        with transaction.atomic():
            order, created = Order.objects.get_or_create(
                so_don_hang=data["code"],
                defaults={
                    "ma_khach_hang": customer,
                    "trang_thai": data["status"],
                    "thoi_diem_dat": timezone.now(),
                    "don_vi_tien_te": "VND",
                },
            )

            if order.ma_khach_hang_id != customer.pk:
                raise ValueError(
                    f"Don {data['code']} da thuoc khach hang khac."
                )

            if order.trang_thai != data["status"]:
                raise ValueError(
                    f"Don {data['code']} co trang thai "
                    f"{order.trang_thai}, khac du kien "
                    f"{data['status']}."
                )

            if created:
                created_orders += 1
            else:
                existing_orders += 1

            for sku, quantity, amount in data["items"]:
                product = product_map[sku]

                existing_items = OrderItem.objects.filter(
                    ma_don_hang=order,
                    ma_san_pham=product,
                )

                if existing_items.count() > 1:
                    raise ValueError(
                        f"Don {data['code']} co nhieu dong "
                        f"trung san pham {sku}."
                    )

                existing_item = existing_items.first()

                if existing_item is not None:
                    if (
                        existing_item.so_luong != quantity
                        or existing_item.gia_tri_da_thanh_toan
                        != Decimal(amount)
                        or existing_item.ten_san_pham_luc_mua
                        != product.ten_san_pham
                    ):
                        raise ValueError(
                            f"Chi tiet don {data['code']} / {sku} "
                            "da ton tai nhung khac du lieu demo."
                        )
                    continue

                OrderItem.objects.create(
                    ma_don_hang=order,
                    ma_san_pham=product,
                    ten_san_pham_luc_mua=product.ten_san_pham,
                    so_luong=quantity,
                    gia_tri_da_thanh_toan=Decimal(amount),
                )

                created_items += 1

        print(
            f"[OK] {data['code']} "
            f"| {data['username']} "
            f"| {data['status']} "
            f"| {data['scenario']}"
        )

    return created_orders, created_items, existing_orders


# ----------------------------------------------------------
# 6. CHAY SEED
# ----------------------------------------------------------

def main():
    print("=" * 75)
    print("CRM HULO - TAO DU LIEU DEMO E2E")
    print("=" * 75)

    # Kiem tra tat ca tai khoan truoc khi ghi DB.
    for username in [
        "khachhang01",
        "khachhang02",
        "khachhang03",
        "khachhang04",
        "khachhang05",
    ]:
        customer = get_customer(username)
        print(
            f"Khach hang hop le: {username} "
            f"- Customer ID {customer.pk}"
        )

    # Mot transaction cho toan bo du lieu:
    # Neu co loi, khong luu bo du lieu dang do.
    with transaction.atomic():
        product_map, new_products = create_products()

        new_orders, new_items, old_orders = create_orders(
            product_map
        )

    print()
    print("=" * 75)
    print("KET QUA")
    print("=" * 75)

    print(f"San pham moi: {new_products}")
    print(f"Don hang moi: {new_orders}")
    print(f"Chi tiet don moi: {new_items}")
    print(f"Don hang da ton tai: {old_orders}")

    print()
    print("Tong san pham trong database:", Product.objects.count())
    print("Tong don hang trong database:", Order.objects.count())
    print("Tong chi tiet don:", OrderItem.objects.count())

    print()
    print("HOAN THANH TAO DU LIEU DEMO CRM HULO")


main()
