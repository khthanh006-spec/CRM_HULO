
"""
Module 3 - Kiem tra anh mo coi.

Mac dinh: chi bao cao.
Tuy chon --quarantine: chuyen file nghi mo coi
sang thu muc cach ly, khong xoa vinh vien.

Khong thay doi Ticket, TicketAttachment, SLA
hoac Smart Routing.
"""

from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from tickets.models import TicketAttachment


class Command(BaseCommand):
    help = "Bao cao hoac cach ly anh TicketAttachment mo coi"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Chi xet file cu hon N gio (mac dinh 24)",
        )
        parser.add_argument(
            "--quarantine",
            action="store_true",
            help="Chuyen file nghi mo coi sang thu muc cach ly",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        quarantine = options["quarantine"]

        if hours < 1:
            raise CommandError(
                "So gio phai lon hon hoac bang 1."
            )

        media_root = Path(settings.MEDIA_ROOT).resolve()
        folder = media_root / "ticket_attachments"

        if not folder.is_dir():
            self.stdout.write(
                "Chua co thu muc ticket_attachments."
            )
            return

        referenced_files = {
            Path(name).as_posix()
            for name in TicketAttachment.objects.exclude(
                tep_dinh_kem=""
            ).values_list("tep_dinh_kem", flat=True)
            if name
        }

        threshold = timedelta(hours=hours).total_seconds()
        now = timezone.now().timestamp()

        suspected_orphans = []

        for file_path in folder.rglob("*"):
            if not file_path.is_file():
                continue

            relative_name = file_path.relative_to(
                media_root
            ).as_posix()

            file_age = now - file_path.stat().st_mtime

            if (
                relative_name not in referenced_files
                and file_age >= threshold
            ):
                suspected_orphans.append(
                    (file_path, relative_name)
                )

        self.stdout.write(
            f"So file nghi mo coi: {len(suspected_orphans)}"
        )

        for _, relative_name in suspected_orphans:
            self.stdout.write(f" - {relative_name}")

        if not quarantine:
            self.stdout.write(
                "Che do bao cao: khong thay doi file."
            )
            return

        quarantine_root = (
            media_root.parent / "CRM_HULO_m3_quarantine"
        ).resolve()

        moved = 0

        for file_path, relative_name in suspected_orphans:
            # Kiem tra lai truoc khi chuyen file.
            still_referenced = TicketAttachment.objects.filter(
                tep_dinh_kem=relative_name
            ).exists()

            if still_referenced or not file_path.is_file():
                continue

            # Moi file co mot ten duy nhat de tranh ghi de.
            target = (
                quarantine_root
                / f"{uuid4().hex}_{file_path.name}"
            )

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.move(str(file_path), str(target))
            moved += 1

            self.stdout.write(
                f"Da cach ly: {relative_name}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Hoan tat. Da cach ly {moved} file."
            )
        )
