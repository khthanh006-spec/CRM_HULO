
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import LoyaltyAccount, LoyaltyTransaction


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
    Xu ly giao dich Loyalty.

    EARN:
        Cong diem kha dung va tong diem tich luy.

    REDEEM:
        Tru diem kha dung.
        Khong tru tong diem tich luy.

    idempotency_key:
        Cung mot ma yeu cau chi xu ly mot lan.
        Neu khong cung cap ma, chua co bao ve
        chong trung cho lan goi do.
    """

    # 1. Kiem tra so diem
    if type(points) is not int or points <= 0:
        raise ValueError(
            "Số điểm phải là số nguyên dương."
        )

    # 2. Kiem tra loai giao dich
    if transaction_type not in LoyaltyTransaction.TransactionType.values:
        raise ValueError(
            "Loại giao dịch Loyalty không hợp lệ."
        )

    # 3. Kiem tra mo ta
    if not isinstance(description, str):
        raise ValueError(
            "Mô tả giao dịch không hợp lệ."
        )

    description = description.strip()

    if len(description) > 255:
        raise ValueError(
            "Mô tả không được quá 255 ký tự."
        )

    # 4. Kiem tra nguoi thuc hien neu duoc truyen
    if performed_by is not None and getattr(performed_by, "pk", None) is None:
        raise ValueError(
            "Người thực hiện không hợp lệ."
        )

    # 5. Chuan hoa ma chong trung
    key = None

    if idempotency_key is not None:
        try:
            key = UUID(str(idempotency_key))
        except (ValueError, TypeError, AttributeError):
            raise ValueError(
                "Mã yêu cầu giao dịch không hợp lệ."
            )

    # 6. Ham kiem tra yeu cau da xu ly
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

        # 7. Thuc hien trong mot giao dich database
        with transaction.atomic():

            # Kiem tra ma yeu cau da ton tai
            if key is not None:

                existing = (
                    LoyaltyTransaction.objects
                    .select_related("account")
                    .filter(idempotency_key=key)
                    .first()
                )

                if existing is not None:
                    return check_existing(existing)

            # 8. Lay tai khoan Loyalty
            account = (
                LoyaltyAccount.objects
                .select_for_update()
                .get(customer=customer)
            )

            # 9. Tao giao dich truoc khi cap nhat diem
            # Unique key ngan hai ban ghi trung ma
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

            # 10. Cong diem
            if transaction_type == LoyaltyTransaction.TransactionType.EARN:

                LoyaltyAccount.objects.filter(
                    pk=account.pk
                ).update(
                    points_balance=F("points_balance") + points,
                    total_points_earned=F("total_points_earned") + points,
                    updated_at=timezone.now()
                )

            # 11. Doi diem
            elif transaction_type == LoyaltyTransaction.TransactionType.REDEEM:

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

            # 12. Tra ket qua
            return loyalty_transaction

    except IntegrityError:

        # Neu hai yeu cau cung ma duoc gui gan nhau,
        # tim giao dich da luu sau khi transaction rollback.
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
