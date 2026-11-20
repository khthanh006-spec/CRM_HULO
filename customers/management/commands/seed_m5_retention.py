
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError

from customers.models import CSAT, RetentionCase
from tickets.models import TicketLog


class Command(BaseCommand):
    help = (
        "Dong bo Retention Case tu CSAT thap "
        "va su kien khach hang mo lai Ticket."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        assigned_count = 0
        existing_count = 0

        try:
            # ==========================================
            # 1. RETENTION TỪ CSAT THẤP (1-2 SAO)
            # ==========================================

            csats = (
                CSAT.objects
                .filter(score__in=[1, 2])
                .select_related(
                    "ticket__khach_hang",
                    "ticket__nguoi_phu_trach",
                    "ticket__nguoi_phu_trach__ma_tai_khoan",
                )
            )

            for csat in csats:
                ticket = csat.ticket

                owner_id = None

                if (
                    ticket.nguoi_phu_trach_id
                    and ticket.nguoi_phu_trach.vai_tro == "CSKH"
                ):
                    owner_id = (
                        ticket.nguoi_phu_trach.ma_tai_khoan_id
                    )

                case, created = RetentionCase.objects.get_or_create(
                    source_csat=csat,
                    defaults={
                        "customer_id": ticket.khach_hang_id,
                        "ticket_id": ticket.pk,
                        "source": "LOW_CSAT",
                        "assigned_to_id": owner_id,
                        "triggered_at": csat.created_at,
                        "trigger_summary": (
                            f"CSAT {csat.score}/5. {csat.comment}"
                        )[:1000],
                    },
                )

                if created:
                    created_count += 1

                elif (
                    case.status == RetentionCase.Status.PENDING
                    and case.assigned_to_id is None
                    and owner_id is not None
                ):
                    case.assigned_to_id = owner_id
                    case.full_clean()
                    case.save(
                        update_fields=[
                            "assigned_to",
                            "updated_at",
                        ]
                    )
                    assigned_count += 1
                else:
                    existing_count += 1

            # ==========================================
            # 2. RETENTION TỪ SỰ KIỆN MỞ LẠI TICKET
            # ==========================================

            logs = (
                TicketLog.objects
                .filter(
                    hanh_dong="KHÁCH HÀNG YÊU CẦU MỞ LẠI"
                )
                .select_related(
                    "ticket__khach_hang",
                    "ticket__nguoi_phu_trach",
                    "ticket__nguoi_phu_trach__ma_tai_khoan",
                )
            )

            for log in logs:
                ticket = log.ticket

                owner_id = None

                if (
                    ticket.nguoi_phu_trach_id
                    and ticket.nguoi_phu_trach.vai_tro == "CSKH"
                ):
                    owner_id = (
                        ticket.nguoi_phu_trach.ma_tai_khoan_id
                    )

                case, created = RetentionCase.objects.get_or_create(
                    source_ticket_log=log,
                    defaults={
                        "customer_id": ticket.khach_hang_id,
                        "ticket_id": ticket.pk,
                        "source": "REOPENED",
                        "assigned_to_id": owner_id,
                        "triggered_at": log.thoi_diem,
                        "trigger_summary": log.noi_dung[:1000],
                    },
                )

                if created:
                    created_count += 1

                elif (
                    case.status == RetentionCase.Status.PENDING
                    and case.assigned_to_id is None
                    and owner_id is not None
                ):
                    case.assigned_to_id = owner_id
                    case.full_clean()
                    case.save(
                        update_fields=[
                            "assigned_to",
                            "updated_at",
                        ]
                    )
                    assigned_count += 1
                else:
                    existing_count += 1

        except (DatabaseError, ValidationError) as error:
            raise Exception(
                f"Khong the dong bo Retention: {error}"
            ) from error

        self.stdout.write("")
        self.stdout.write("========== KET QUA RETENTION ==========")
        self.stdout.write(f"Ca moi: {created_count}")
        self.stdout.write(f"Ca duoc bo sung CSKH: {assigned_count}")
        self.stdout.write(f"Ca da ton tai: {existing_count}")

        self.stdout.write(
            self.style.SUCCESS(
                "Hoan tat seed Retention M5!"
            )
        )
