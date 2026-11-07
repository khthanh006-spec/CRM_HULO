
from uuid import UUID, uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    AfterSalesBenefit,
    AfterSalesDelivery,
    AfterSalesProgram,
    Customer,
    LoyaltyAccount,
    LoyaltyRedemption,
    LoyaltyReward,
    LoyaltyTier,
)
from .services import redeem_loyalty_voucher


# ==============================================
# MODULE 5 - CUSTOMER LOYALTY OFFERS
# ==============================================

@login_required
@require_http_methods(["GET", "POST"])
def my_offers(request):

    # Chỉ lấy hồ sơ của người đang đăng nhập.
    # Không nhận customer_id từ trình duyệt.
    customer = get_object_or_404(
        Customer,
        ma_tai_khoan=request.user,
    )

    # ==========================================
    # 1. KHÁCH HÀNG TỰ ĐỔI ĐIỂM LẤY VOUCHER
    # ==========================================

    session_key = "customer_loyalty_redeem_token"

    if request.method == "POST":

        action = request.POST.get("action", "").strip()

        if action != "redeem_voucher":
            messages.error(
                request,
                "Yêu cầu không hợp lệ.",
            )
            return redirect("customers:my_vouchers")

        reward_id = request.POST.get(
            "reward_id", ""
        ).strip()

        submitted_token = request.POST.get(
            "redeem_token", ""
        ).strip()

        session_token = request.session.get(
            session_key
        )

        # Kiểm tra mã yêu cầu có đúng với
        # phiên làm việc hiện tại hay không.
        if (
            not session_token
            or submitted_token != session_token
        ):
            messages.error(
                request,
                "Yêu cầu đã hết hiệu lực hoặc đã được "
                "xử lý. Vui lòng tải lại trang.",
            )
            return redirect("customers:my_vouchers")

        try:
            request_uuid = UUID(submitted_token)
        except (ValueError, TypeError, AttributeError):
            messages.error(
                request,
                "Mã yêu cầu đổi Voucher không hợp lệ.",
            )
            return redirect("customers:my_vouchers")

        try:
            reward_pk = int(reward_id)
        except (ValueError, TypeError):
            messages.error(
                request,
                "Voucher được chọn không hợp lệ.",
            )
            return redirect("customers:my_vouchers")

        if reward_pk <= 0:
            messages.error(
                request,
                "Voucher được chọn không hợp lệ.",
            )
            return redirect("customers:my_vouchers")

        reward = (
            LoyaltyReward.objects
            .filter(
                pk=reward_pk,
                is_enabled=True,
            )
            .first()
        )

        if reward is None:
            messages.error(
                request,
                "Voucher này không còn được phép đổi.",
            )
            return redirect("customers:my_vouchers")

        # Mô tả không lấy từ dữ liệu người dùng
        # để tránh thay đổi nội dung giao dịch.
        description = (
            f"Đổi điểm lấy voucher: {reward.name}"
        )

        # Service yêu cầu mô tả từ 5 đến 240 ký tự.
        if len(description) > 240:
            messages.error(
                request,
                "Tên Voucher quá dài, không thể "
                "tạo giao dịch đổi điểm.",
            )
            return redirect("customers:my_vouchers")

        try:
            redemption, created = redeem_loyalty_voucher(
                customer=customer,
                reward_id=reward.pk,
                description=description,
                performed_by=request.user,
                idempotency_key=request_uuid,
            )

        except LoyaltyAccount.DoesNotExist:
            messages.error(
                request,
                "Bạn chưa có tài khoản Loyalty. "
                "Vui lòng liên hệ HULO để được hỗ trợ.",
            )
            return redirect("customers:my_vouchers")

        except ValueError as exc:
            messages.error(
                request,
                str(exc),
            )
            return redirect("customers:my_vouchers")

        # Sau khi xử lý thành công, vô hiệu hóa
        # token của biểu mẫu vừa gửi.
        # Yêu cầu đổi tiếp theo phải sử dụng
        # token mới.
        request.session[session_key] = str(uuid4())

        if created:
            messages.success(
                request,
                "Đổi Voucher thành công! "
                f"Bạn đã nhận được {redemption.voucher_name}. "
                "Voucher đã được thêm vào tài khoản.",
            )
        else:
            messages.info(
                request,
                "Yêu cầu này đã được xử lý trước đó. "
                "Voucher đã có trong tài khoản của bạn.",
            )

        return redirect("customers:my_vouchers")

    # ==========================================
    # 2. CHUẨN BỊ MÃ YÊU CẦU ĐỔI VOUCHER
    # ==========================================

    redeem_token = request.session.get(
        session_key
    )

    if not redeem_token:
        redeem_token = str(uuid4())
        request.session[session_key] = redeem_token

    account = (
        LoyaltyAccount.objects
        .filter(customer=customer)
        .select_related("tier")
        .first()
    )

    # ==========================================
    # 3. ĐIỂM VÀ HẠNG THÀNH VIÊN
    # ==========================================

    tiers = list(
        LoyaltyTier.objects.order_by(
            "min_total_points",
            "pk",
        )
    )

    earned = (
        account.total_points_earned
        if account else 0
    )

    balance = (
        account.points_balance
        if account else 0
    )

    current_tier = (
        account.tier
        if account else None
    )

    next_tier = next(
        (
            tier for tier in tiers
            if tier.min_total_points > earned
        ),
        None,
    )

    progress = 100
    points_needed = 0

    if next_tier:

        floor = (
            current_tier.min_total_points
            if current_tier else 0
        )

        span = max(
            1,
            next_tier.min_total_points - floor,
        )

        progress = max(
            0,
            min(
                100,
                round(
                    (earned - floor) * 100 / span
                ),
            ),
        )

        points_needed = max(
            0,
            next_tier.min_total_points - earned,
        )

    # ==========================================
    # 4. VOUCHER ĐƯỢC NHÂN VIÊN CẤP
    # ==========================================

    now = timezone.now()
    voucher_rows = []

    deliveries = (
        AfterSalesDelivery.objects
        .filter(
            customer=customer,
            issued_at__isnull=False,
            benefit__benefit_type=(
                AfterSalesBenefit.BenefitType.VOUCHER
            ),
        )
        .select_related(
            "benefit",
            "benefit__program",
        )
        .order_by("-issued_at", "-pk")
    )

    for delivery in deliveries:

        benefit = delivery.benefit

        if not benefit.is_enabled:
            status = "Tạm dừng"
            badge = "paused"

        elif now < benefit.valid_from:
            status = "Chưa đến hạn"
            badge = "upcoming"

        elif now > benefit.valid_until:
            status = "Hết hạn"
            badge = "expired"

        else:
            status = "Trong thời hạn"
            badge = "active"

        voucher_rows.append({
            "kind": "staff",
            "title": benefit.name,
            "source": "Voucher được cấp",
            "description": benefit.description,
            "code": delivery.reference_code,
            "issued_at": delivery.issued_at,
            "expires_at": benefit.valid_until,
            "valid_from": benefit.valid_from,
            "terms": benefit.terms,
            "status": status,
            "badge": badge,
            "program": benefit.program.name,
        })

    # ==========================================
    # 5. VOUCHER ĐỔI BẰNG ĐIỂM
    # ==========================================

    redemptions = (
        LoyaltyRedemption.objects
        .filter(
            transaction__account__customer=customer,
        )
        .select_related("transaction")
        .order_by("-issued_at", "-pk")
    )

    for redemption in redemptions:

        expired = now > redemption.expires_at

        voucher_rows.append({
            "kind": "points",
            "title": redemption.voucher_name,
            "source": "Voucher đổi bằng điểm",
            "description": "",
            "code": redemption.reference_code,
            "issued_at": redemption.issued_at,
            "expires_at": redemption.expires_at,
            "valid_from": redemption.issued_at,
            "terms": redemption.terms,
            "status": (
                "Hết hạn"
                if expired else "Trong thời hạn"
            ),
            "badge": (
                "expired"
                if expired else "active"
            ),
            "discount_amount": (
                redemption.discount_amount
            ),
            "points_spent": (
                redemption.points_spent
            ),
        })

    voucher_rows.sort(
        key=lambda row: row["issued_at"],
        reverse=True,
    )

    # ==========================================
    # 6. LỊCH SỬ GIAO DỊCH ĐIỂM
    # ==========================================

    transactions = (
        account.transactions
        .order_by("-created_at", "-pk")[:50]
        if account else []
    )

    # ==========================================
    # 7. DANH SÁCH VOUCHER CÓ THỂ ĐỔI
    # ==========================================

    rewards = (
        LoyaltyReward.objects
        .filter(is_enabled=True)
        .order_by("points_cost", "pk")
    )

    # ==========================================
    # 8. CHƯƠNG TRÌNH ƯU ĐÃI
    # ==========================================

    programs = (
        AfterSalesProgram.objects
        .filter(
            is_enabled=True,
            ends_at__gte=now,
        )
        .prefetch_related("eligible_tiers")
        .order_by("starts_at", "pk")
    )

    eligible_programs = []

    for program in programs:

        eligible_ids = {
            tier.pk
            for tier in program.eligible_tiers.all()
        }

        if eligible_ids and (
            not current_tier
            or current_tier.pk not in eligible_ids
        ):
            continue

        eligible_programs.append({
            "program": program,
            "status": (
                "Sắp diễn ra"
                if now < program.starts_at
                else "Đang diễn ra"
            ),
        })

    # ==========================================
    # 9. CHỌN TAB HIỂN THỊ
    # ==========================================

    tab = request.GET.get(
        "tab",
        "vouchers",
    )

    if tab not in (
        "vouchers",
        "tiers",
        "history",
        "programs",
    ):
        tab = "vouchers"

    # ==========================================
    # 10. TRẢ DỮ LIỆU RA GIAO DIỆN
    # ==========================================

    return render(
        request,
        "customers/my_vouchers.html",
        {
            "customer": customer,
            "account": account,
            "balance": balance,
            "earned": earned,
            "current_tier": current_tier,
            "next_tier": next_tier,
            "progress": progress,
            "points_needed": points_needed,
            "tiers": tiers,
            "voucher_rows": voucher_rows,
            "voucher_count": len(voucher_rows),
            "transactions": transactions,
            "rewards": rewards,
            "program_rows": eligible_programs,
            "tab": tab,
            "redeem_token": redeem_token,
        },
    )
