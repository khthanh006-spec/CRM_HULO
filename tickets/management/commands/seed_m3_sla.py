
from django.core.management.base import BaseCommand
from django.db import transaction

from tickets.models import (
    TicketCategory,
    TicketCategoryQueue,
    TicketQueue,
    SLAConfig,
)


SLA_HOURS = {
    "LOW": 72,
    "MEDIUM": 48,
    "HIGH": 24,
    "URGENT": 4,
}

CATEGORIES = [
    "Hàng bị lỗi",
    "Lỗi in ấn",
    "Sai thiết kế cá nhân hóa",
    "Sai sản phẩm / đơn hàng",
    "Thiếu sản phẩm / phụ kiện",
    "Chậm sản xuất",
    "Chậm giao hàng",
    "Hư hỏng khi vận chuyển",
    "Đổi trả / Hoàn tiền",
    "Hủy / Thay đổi đơn hàng",
    "Thanh toán / Hóa đơn",
    "Bảo hành / Hậu mãi",
    "Khiếu nại dịch vụ",
]

M3_QUEUE_NAME = "M3 - Tiếp nhận và xử lý Ticket"


class Command(BaseCommand):
    help = "Khoi tao 52 SLA va lien ket 13 danh muc voi queue M3."

    @transaction.atomic
    def handle(self, *args, **options):
        queue, _ = TicketQueue.objects.get_or_create(
            ten_queue=M3_QUEUE_NAME,
            defaults={
                "mo_ta": (
                    "Hàng đợi tiếp nhận và xử lý Ticket từ Chatbot M2."
                ),
                "dang_hoat_dong": True,
            },
        )

        if not queue.dang_hoat_dong:
            self.stdout.write(
                self.style.WARNING(
                    "Queue M3 dang bi tat. Khong tu dong kich hoat."
                )
            )

        sla_created = 0
        sla_updated = 0
        mapping_created = 0
        mapping_updated = 0

        for category_name in CATEGORIES:
            category, _ = TicketCategory.objects.get_or_create(
                ten_danh_muc=category_name,
                defaults={
                    "mo_ta": "Danh mục hỗ trợ khách hàng từ Chatbot M2",
                    "dang_hoat_dong": True,
                },
            )

            _, mapping_is_new = TicketCategoryQueue.objects.update_or_create(
                danh_muc=category,
                defaults={"queue": queue},
            )

            if mapping_is_new:
                mapping_created += 1
            else:
                mapping_updated += 1

            for priority, hours in SLA_HOURS.items():
                _, sla_is_new = SLAConfig.objects.update_or_create(
                    danh_muc=category,
                    muc_uu_tien=priority,
                    defaults={
                        "thoi_han_gio": hours,
                        "dang_hoat_dong": True,
                    },
                )

                if sla_is_new:
                    sla_created += 1
                else:
                    sla_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Hoan thanh seed M3!\n"
                f"SLA: {sla_created} tao moi, "
                f"{sla_updated} cap nhat.\n"
                f"Queue mapping: {mapping_created} tao moi, "
                f"{mapping_updated} cap nhat."
            )
        )
