
from pathlib import Path
import runpy

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Khoi tao bo du lieu demo tong the CRM HULO M1-M5"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("=== CRM HULO - SEED DU LIEU DEMO ===")

        # 1. Tài khoản và hồ sơ
        self.stdout.write("\n[1/7] Tai khoan va ho so")
        call_command("seed_demo")

        # 2. Khách hàng và Loyalty M5
        self.stdout.write("\n[2/7] Khach hang va Loyalty M5")
        call_command("seed_m5_customers")

        # 3. Sản phẩm và đơn hàng
        self.stdout.write("\n[3/7] San pham va don hang")
        project_root = Path(__file__).resolve().parents[3]
        order_seed = project_root / "seed_demo_orders.py"

        if not order_seed.is_file():
            raise FileNotFoundError(
                f"Khong tim thay file: {order_seed}"
            )

        runpy.run_path(str(order_seed))

        # 4. Queue, danh mục và SLA M3
        self.stdout.write("\n[4/7] Cau hinh M3")
        call_command("seed_m3_sla")

        # 5. Ticket và CSAT M5
        self.stdout.write("\n[5/7] Ticket va CSAT")
        call_command("seed_m5_tickets")

        # 6. Hồ sơ thẩm định M4
        self.stdout.write("\n[6/7] Ho so tham dinh M4")
        call_command("seed_m4_test_cases")

        # 7. Retention M5
        self.stdout.write("\n[7/7] Retention M5")
        call_command("seed_m5_retention")

        self.stdout.write(
            self.style.SUCCESS(
                "\nDa hoan thanh cac lenh seed demo CRM HULO."
            )
        )
