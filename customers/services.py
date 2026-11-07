
from datetime import timedelta
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    LoyaltyAccount,
    LoyaltyTransaction,
    LoyaltyTier,
    LoyaltyReward,
    LoyaltyRedemption,
)


# ==============================================
# MODULE 5 - LOYALTY POINT SERVICE
# ==============================================

def change_loyalty_points(
    *,
    customer,
    transaction_type,
    points,
    description="",
    performed_by=None,
    idempotency_key=None
):
    """
    Xử lý giao dịch Loyalty.

    EARN:
        Cộng điểm khả dụng và tổng điểm tích lũy.

    REDEEM:
        Trừ điểm khả dụng.
        Không trừ tổng điểm tích lũy.

    idempotency_key:
        Cùng một mã yêu cầu chỉ xử lý một lần.
        Nếu không cung cấp mã, chưa có bảo vệ
        chống trùng cho lần gọi đó.
    """

    # 1. Kiểm tra số điểm
    if type(points) is not int or points <= 0:
        raise ValueError(
            "Số điểm phải là số nguyên dương."
        )

    # 2. Kiểm tra loại giao dịch
    if transaction_type not in LoyaltyTransaction.TransactionType.values:
        raise ValueError(
            "Loại giao dịch Loyalty không hợp lệ."
        )

    # 3. Kiểm tra mô tả
    if not isinstance(description, str):
        raise ValueError(
            "Mô tả giao dịch không hợp lệ."
        )

    description = description.strip()

    if len(description) > 255:
        raise ValueError(
            "Mô tả không được quá 255 ký tự."
        )

    # 4. Kiểm tra người thực hiện nếu được truyền
    if (
        performed_by is not None
        and getattr(performed_by, "pk", None) is None
    ):
        raise ValueError(
            "Người thực hiện không hợp lệ."
        )

    # 5. Chuẩn hóa mã chống trùng
    key = None

    if idempotency_key is not None:
        try:
            key = UUID(str(idempotency_key))
        except (ValueError, TypeError, AttributeError):
            raise ValueError(
                "Mã yêu cầu giao dịch không hợp lệ."
            )

    # 6. Hàm kiểm tra yêu cầu đã xử lý
    def check_existing(existing):

        if (
            existing.account.customer_id != customer.pk
            or existing.transaction_type != transaction_type
            or existing.points != points
            or existing.description != description
        ):
            raise ValueError(
                "Mã giao dịch đã được dùng cho một yêu cầu khác."
            )

        return existing

    try:

        # 7. Thực hiện trong một giao dịch database
        with transaction.atomic():

            # Kiểm tra mã yêu cầu đã tồn tại
            if key is not None:

                existing = (
                    LoyaltyTransaction.objects
                    .select_related("account")
                    .filter(idempotency_key=key)
                    .first()
                )

                if existing is not None:
                    return check_existing(existing)

            # 8. Lấy tài khoản Loyalty
            account = (
                LoyaltyAccount.objects
                .select_for_update()
                .get(customer=customer)
            )

            # 9. Tạo giao dịch trước khi cập nhật điểm
            # Unique key ngăn hai bản ghi trùng mã
            loyalty_transaction = (
                LoyaltyTransaction.objects.create(
                    account=account,
                    transaction_type=transaction_type,
                    points=points,
                    description=description,
                    performed_by=performed_by,
                    idempotency_key=key
                )
            )

            # 10. Cộng điểm và cập nhật hạng
            if (
                transaction_type
                == LoyaltyTransaction.TransactionType.EARN
            ):

                LoyaltyAccount.objects.filter(
                    pk=account.pk
                ).update(
                    points_balance=F("points_balance") + points,
                    total_points_earned=F("total_points_earned") + points,
                    updated_at=timezone.now(),
                )

                account.refresh_from_db()

                new_tier = (
                    LoyaltyTier.objects
                    .filter(
                        min_total_points__lte=account.total_points_earned
                    )
                    .order_by("-min_total_points")
                    .first()
                )

                if new_tier is not None:
                    LoyaltyAccount.objects.filter(
                        pk=account.pk
                    ).update(tier=new_tier)

                    account.tier = new_tier

            # 11. Đổi điểm
            elif (
                transaction_type
                == LoyaltyTransaction.TransactionType.REDEEM
            ):

                updated = (
                    LoyaltyAccount.objects
                    .filter(
                        pk=account.pk,
                        points_balance__gte=points
                    )
                    .update(
                        points_balance=F("points_balance") - points,
                        updated_at=timezone.now()
                    )
                )

                if updated == 0:
                    raise ValueError(
                        "Khách hàng không đủ điểm để đổi."
                    )

            # 12. Trả kết quả
            return loyalty_transaction

    except IntegrityError:

        # Nếu hai yêu cầu cùng mã được gửi gần nhau,
        # tìm giao dịch đã lưu sau khi transaction rollback.
        if key is None:
            raise

        existing = (
            LoyaltyTransaction.objects
            .select_related("account")
            .filter(idempotency_key=key)
            .first()
        )

        if existing is None:
            raise

        return check_existing(existing)


# ==============================================
# MODULE 5 - LOYALTY VOUCHER REDEMPTION
# ==============================================

def redeem_loyalty_voucher(
    *,
    customer,
    reward_id,
    description,
    performed_by,
    idempotency_key,
):
    """
    Trừ điểm và tạo Voucher trong cùng giao dịch.

    Giao dịch mới không có tiền tố DEMO.

    Các yêu cầu cũ đã được lưu với tiền tố DEMO
    vẫn được nhận diện khi gửi lại cùng mã yêu cầu.

    Gửi lại cùng yêu cầu trả về Voucher đã tạo,
    không trừ điểm lần thứ hai.
    """

    if performed_by is None or performed_by.pk is None:
        raise ValueError(
            "Người thực hiện không hợp lệ."
        )

    try:
        key = UUID(str(idempotency_key))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(
            "Mã yêu cầu không hợp lệ."
        )

    if not isinstance(description, str):
        raise ValueError(
            "Lý do giao dịch không hợp lệ."
        )

    description = description.strip()

    if not 5 <= len(description) <= 240:
        raise ValueError(
            "Lý do cần từ 5 đến 240 ký tự."
        )

    # Không thêm tiền tố DEMO cho giao dịch mới.
    transaction_description = description

    # Chỉ sử dụng để tương thích giao dịch cũ.
    legacy_description = "DEMO - " + description

    with transaction.atomic():

        # Khóa tài khoản trước khi kiểm tra và trừ điểm.
        account = (
            LoyaltyAccount.objects
            .select_for_update()
            .get(customer=customer)
        )

        existing = (
            LoyaltyTransaction.objects
            .filter(idempotency_key=key)
            .first()
        )

        if existing is not None:

            redemption = (
                LoyaltyRedemption.objects
                .filter(transaction=existing)
                .first()
            )

            # Chấp nhận mô tả mới hoặc định dạng cũ
            # khi kiểm tra lại một yêu cầu đã xử lý.
            valid_description = existing.description in (
                transaction_description,
                legacy_description,
            )

            if (
                existing.account_id != account.pk
                or existing.transaction_type != 'REDEEM'
                or not valid_description
                or existing.performed_by_id != performed_by.pk
                or redemption is None
                or redemption.reward_id != reward_id
            ):
                raise ValueError(
                    "Mã yêu cầu đã được dùng cho giao dịch khác."
                )

            return redemption, False

        reward = (
            LoyaltyReward.objects
            .select_for_update()
            .filter(pk=reward_id)
            .first()
        )

        if reward is None or not reward.is_enabled:
            raise ValueError(
                "Voucher không còn được phép đổi."
            )

        if (
            reward.points_cost < 1
            or reward.discount_amount < 1
            or reward.validity_days < 1
        ):
            raise ValueError(
                "Cấu hình Voucher không hợp lệ."
            )

        if account.points_balance < reward.points_cost:
            raise ValueError(
                "Khách hàng không đủ điểm đổi Voucher."
            )

        point_transaction = change_loyalty_points(
            customer=customer,
            transaction_type='REDEEM',
            points=reward.points_cost,
            description=transaction_description,
            performed_by=performed_by,
            idempotency_key=key,
        )

        now = timezone.now()

        redemption = LoyaltyRedemption.objects.create(
            transaction=point_transaction,
            reward=reward,
            voucher_name=reward.name,
            points_spent=reward.points_cost,
            discount_amount=reward.discount_amount,
            terms=reward.terms,
            issued_at=now,
            expires_at=now + timedelta(
                days=reward.validity_days
            ),
        )

        return redemption, True
