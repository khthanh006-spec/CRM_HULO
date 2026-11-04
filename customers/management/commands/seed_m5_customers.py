from getpass import getpass
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from customers.models import (
    Customer,
    LoyaltyTier,
    LoyaltyAccount,
    LoyaltyTransaction,
    CareRecord,
)


# Ngưỡng đề xuất cho demo, chỉ dùng khi hạng chưa tồn tại.
TIER_DEFAULTS = [
    ('MEMBER', 0),
    ('SILVER', 500),
    ('GOLD', 1500),
    ('PLATINUM', 3000),
]


# username, họ tên, hạng, địa chỉ minh họa
CUSTOMERS = [
    (
        'm5_demo_01',
        'Nguyễn Minh Anh',
        'MEMBER',
        'Hải Châu, Đà Nẵng',
    ),
    (
        'm5_demo_02',
        'Trần Ngọc Hà',
        'MEMBER',
        'Thanh Khê, Đà Nẵng',
    ),
    (
        'm5_demo_03',
        'Lê Hoàng Nam',
        'MEMBER',
        'Sơn Trà, Đà Nẵng',
    ),
    (
        'm5_demo_04',
        'Phạm Thu Trang',
        'SILVER',
        'Cẩm Lệ, Đà Nẵng',
    ),
    (
        'm5_demo_05',
        'Hoàng Gia Bảo',
        'SILVER',
        'Liên Chiểu, Đà Nẵng',
    ),
    (
        'm5_demo_06',
        'Đặng Khánh Linh',
        'SILVER',
        'Ngũ Hành Sơn, Đà Nẵng',
    ),
    (
        'm5_demo_07',
        'Võ Đức Huy',
        'GOLD',
        'Hải Châu, Đà Nẵng',
    ),
    (
        'm5_demo_08',
        'Bùi Thảo Vy',
        'GOLD',
        'Sơn Trà, Đà Nẵng',
    ),
    (
        'm5_demo_09',
        'Đỗ Tuấn Kiệt',
        'PLATINUM',
        'Thanh Khê, Đà Nẵng',
    ),
    (
        'm5_demo_10',
        'Nguyễn Hải Yến',
        'PLATINUM',
        'Cẩm Lệ, Đà Nẵng',
    ),
]


class Command(BaseCommand):
    help = (
        'Tạo 10 khách hàng demo M5 cùng tài khoản, '
        'Loyalty và lịch sử chăm sóc.'
    )

    def handle(self, *args, **options):
        User = get_user_model()

        if User.USERNAME_FIELD != 'username':
            raise CommandError(
                'Lệnh mẫu này yêu cầu User dùng username '
                'để đăng nhập.'
            )

        # Khách hàng đã tạo ở lần trước được bỏ qua.
        pending_rows = []

        for row in CUSTOMERS:
            username = row[0]
            email = f'{username}@example.com'

            if Customer.objects.filter(email=email).exists():
                self.stdout.write(
                    f'Bỏ qua email đã tồn tại: {email}'
                )
                continue

            # Không tự liên kết với tài khoản có sẵn.
            if User.objects.filter(username=username).exists():
                raise CommandError(
                    f'Tài khoản {username} đã tồn tại nhưng '
                    'chưa có hồ sơ demo tương ứng. '
                    'Dừng để tránh liên kết nhầm.'
                )

            if User.objects.filter(email=email).exists():
                raise CommandError(
                    f'Email {email} đã thuộc một tài khoản. '
                    'Dừng để tránh trùng dữ liệu.'
                )

            pending_rows.append(row)

        if not pending_rows:
            self.stdout.write(
                self.style.SUCCESS(
                    'Các email demo đã tồn tại. '
                    'Không tạo thêm hoặc thay đổi dữ liệu.'
                )
            )
            return

        self.stdout.write(
            f'Sẽ tạo {len(pending_rows)} khách hàng demo.'
        )

        password = getpass(
            'Nhập mật khẩu chung cho tài khoản demo mới: '
        )
        confirmation = getpass('Nhập lại mật khẩu: ')

        if password != confirmation:
            raise CommandError('Hai mật khẩu không khớp.')

        if not password:
            raise CommandError('Mật khẩu không được để trống.')

        # Kiểm tra theo cấu hình mật khẩu của dự án.
        try:
            for username, name, tier_code, address in pending_rows:
                candidate = User(
                    username=username,
                    email=f'{username}@example.com',
                )
                validate_password(password, user=candidate)

        except ValidationError as error:
            raise CommandError(
                '\n'.join(error.messages)
            ) from error

        created_rows = []

        # Nếu có lỗi, toàn bộ dữ liệu của lần chạy được hoàn tác.
        with transaction.atomic():
            tiers = {}

            for code, threshold in TIER_DEFAULTS:
                tier, created = LoyaltyTier.objects.get_or_create(
                    code=code,
                    defaults={
                        'min_total_points': threshold,
                        'benefits': (
                            'Hạng thành viên dùng trong '
                            'chương trình Loyalty HULO.'
                        ),
                    },
                )
                tiers[code] = tier

            # Bảo đảm thứ tự hạng phù hợp với ngưỡng đang dùng.
            thresholds = [
                tiers[code].min_total_points
                for code, default in TIER_DEFAULTS
            ]

            if (
                thresholds[0] != 0
                or any(
                    left >= right
                    for left, right in zip(
                        thresholds,
                        thresholds[1:],
                    )
                )
            ):
                raise CommandError(
                    'Ngưỡng hạng hiện tại chưa phù hợp: '
                    'Member phải bằng 0 và '
                    'Member < Silver < Gold < Platinum. '
                    'Lệnh không thay đổi ngưỡng đang có.'
                )

            for username, name, tier_code, address in pending_rows:
                email = f'{username}@example.com'
                tier = tiers[tier_code]

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                )

                customer = Customer.objects.create(
                    ma_tai_khoan=user,
                    ho_ten=name,
                    email=email,
                    dia_chi_mac_dinh=(
                        f'[DỮ LIỆU DEMO] {address}'
                    ),
                )

                # Dùng ngưỡng thực tế của hạng.
                # Số dư bằng tổng tích lũy vì chưa có đổi điểm.
                points = tier.min_total_points

                account = LoyaltyAccount.objects.create(
                    customer=customer,
                    tier=tier,
                    points_balance=points,
                    total_points_earned=points,
                )

                # Ghi giao dịch đầu kỳ để điểm có lịch sử đối chiếu.
                if points > 0:
                    LoyaltyTransaction.objects.create(
                        account=account,
                        transaction_type=(
                            LoyaltyTransaction
                            .TransactionType.EARN
                        ),
                        points=points,
                        description=(
                            'DEMO M5 - Điểm đầu kỳ '
                            'của bộ dữ liệu mẫu'
                        ),
                        idempotency_key=uuid5(
                            NAMESPACE_URL,
                            f'hulo:m5:seed:{username}:opening',
                        ),
                    )

                CareRecord.objects.create(
                    customer=customer,
                    care_type=CareRecord.CareType.NOTE,
                    content=(
                        '[DEMO M5] Hồ sơ mẫu phục vụ kiểm tra '
                        'tìm kiếm khách hàng, Customer 360°, '
                        'Loyalty và cấp Voucher. '
                        'Chưa ghi nhận liên hệ thực tế.'
                    ),
                )

                created_rows.append(
                    (
                        username,
                        name,
                        tier.get_code_display(),
                        points,
                    )
                )

        for username, name, tier_name, points in created_rows:
            self.stdout.write(
                f'{username} | {name} | '
                f'{tier_name} | {points} điểm'
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Đã tạo {len(created_rows)} khách hàng demo. '
                'Khách hàng và tài khoản có sẵn được giữ nguyên.'
            )
        )