
"""
Kiem tra file TicketAttachment khong con duoc DB tham chieu.

CHI BAO CAO - KHONG XOA FILE.
"""

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from tickets.models import TicketAttachment


class Command(BaseCommand):
    help = "Kiem tra file anh mo coi cua M3 (khong xoa file)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Chi bao cao file cu hon N gio (mac dinh 24)",
        )

    def handle(self, *args, **options):
        hours = options["hours"]

        if hours < 1:
            self.stderr.write(
                "So gio phai lon hon hoac bang 1."
            )
            return

        media_root = Path(settings.MEDIA_ROOT).resolve()
        folder = media_root / "ticket_attachments"

        if not folder.exists():
            self.stdout.write(
                "Chua co thu muc ticket_attachments."
            )
            return

        # Chi so sanh ten file trong pham vi TicketAttachment.
        files_in_db = {
            Path(name).as_posix()
            for name in TicketAttachment.objects.exclude(
                tep_dinh_kem=""
            ).values_list(
                "tep_dinh_kem",
                flat=True,
            )
            if name
        }

        now = timezone.now().timestamp()
        threshold = timedelta(hours=hours).total_seconds()

        orphan_files = []

        for file_path in folder.rglob("*"):
            if not file_path.is_file():
                continue

            relative_path = file_path.relative_to(
                media_root
            ).as_posix()

            age_seconds = now - file_path.stat().st_mtime

            if (
                relative_path not in files_in_db
                and age_seconds >= threshold
            ):
                orphan_files.append(relative_path)

        self.stdout.write(
            f"So file nghi mo coi: {len(orphan_files)}"
        )

        for name in orphan_files:
            self.stdout.write(f" - {name}")

        self.stdout.write(
            self.style.SUCCESS(
                "Da kiem tra xong. Khong co file nao bi xoa."
            )
        )
