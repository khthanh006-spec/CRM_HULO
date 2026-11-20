
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Staff
from customers.models import Customer, CSAT
from tickets.models import (
    Ticket,
    TicketCategory,
    TicketQueue,
    TicketCategoryQueue,
    TicketLog,
    SLAConfig,
)


# 6 tình huống nghiệp vụ POD
# Mã khách hàng, tên danh mục, trạng thái,
# mức ưu tiên, CSAT, tiêu đề, nội dung

SCENARIOS = [
    (
        "khachhang01",
        "Lỗi in ấn",
        "CLOSED",
        "HIGH",
        2,
        "Khách hàng phản ánh hình in bị nhòe",
        "Khách hàng nhận được áo thun in theo yêu cầu. "
        "Hình in trên sản phẩm bị nhòe so với thiết kế "
        "đã xác nhận. Khách hàng đề nghị kiểm tra và "
        "đưa ra phương án đổi sản phẩm.",
        "Đã xác minh thông tin đơn hàng, tiếp nhận "
        "hình ảnh sản phẩm và chuyển bộ phận chuyên môn "
        "kiểm tra. Đã thống nhất phương án xử lý với khách.",
    ),
    (
        "khachhang02",
        "Thiếu sản phẩm / phụ kiện",
        "IN_PROGRESS",
        "MEDIUM",
        None,
        "Khách hàng nhận thiếu sản phẩm trong đơn",
        "Khách hàng phản ánh kiện hàng chỉ có một phần "
        "sản phẩm theo đơn đặt hàng. Đề nghị kiểm tra "
        "quy trình đóng gói và bổ sung sản phẩm còn thiếu.",
        "",
    ),
    (
        "khachhang03",
        "Sai thiết kế cá nhân hóa",
        "ASSIGNED",
        "HIGH",
        None,
        "Sản phẩm chưa đúng thiết kế đã xác nhận",
        "Khách hàng phản ánh tên cá nhân hóa trên sản phẩm "
        "không đúng nội dung đã gửi khi đặt hàng. "
        "Đề nghị đối chiếu file thiết kế và thông tin đặt hàng.",
        "",
    ),
    (
        "khachhang04",
        "Chậm giao hàng",
        "CLOSED",
        "MEDIUM",
        5,
        "Khách hàng yêu cầu kiểm tra tiến độ giao hàng",
        "Đơn hàng đã hoàn tất sản xuất nhưng thời gian "
        "vận chuyển kéo dài hơn dự kiến. Khách hàng liên hệ "
        "để kiểm tra tiến độ giao nhận.",
        "Đã kiểm tra trạng thái vận chuyển, cập nhật "
        "thông tin cho khách hàng và xác nhận đơn hàng "
        "đã được giao thành công.",
    ),
    (
        "khachhang05",
        "Hàng bị lỗi",
        "RESOLVED",
        "HIGH",
        None,
        "Khách hàng phản ánh sản phẩm có lỗi chất lượng",
        "Khách hàng nhận sản phẩm có lỗi tại phần đường may "
        "và bề mặt vải. Đề nghị kiểm tra chất lượng sản phẩm "
        "và hỗ trợ phương án khắc phục.",
        "Đã tiếp nhận hình ảnh, kiểm tra thông tin sản phẩm "
        "và chuyển kết quả xác minh cho khách hàng. "
        "Đang chờ khách xác nhận phương án xử lý.",
    ),
    (
        "m5_demo_01",
        "Đổi trả / Hoàn tiền",
        "REOPENED",
        "URGENT",
        None,
        "Khách hàng yêu cầu xem xét lại kết quả đổi trả",
        "Khách hàng chưa đồng ý với phương án đổi trả "
        "đã được thông báo trước đó và yêu cầu kiểm tra lại "
        "tình trạng sản phẩm cùng chính sách hỗ trợ.",
        "",
    ),
]


class Command(BaseCommand):
    help = (
        "Khởi tạo 6 Ticket nghiệp vụ POD phục vụ kiểm thử M5. "
        "Không tạo danh mục hoặc Queue mới."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--staff",
            default="cskh01",
            help="Nhân viên CSKH phụ trách.",
        )

    @transaction.atomic
    def handle(self, *args, **options):

        staff = (
            Staff.objects
            .select_related("ma_tai_khoan")
            .filter(
                ma_tai_khoan__username=options["staff"],
                ma_tai_khoan__is_active=True,
                vai_tro="CSKH",
            )
            .first()
        )

        if staff is None:
            raise CommandError(
                "Không tìm thấy nhân viên CSKH đang hoạt động."
            )

        customers = {
            customer.ma_tai_khoan.username: customer
            for customer in Customer.objects.select_related(
                "ma_tai_khoan"
            ).filter(
                ma_tai_khoan__username__in={
                    scenario[0] for scenario in SCENARIOS
                }
            )
        }

        missing = {
            scenario[0] for scenario in SCENARIOS
        } - set(customers)

        if missing:
            raise CommandError(
                "Thiếu tài khoản khách hàng: "
                + ", ".join(sorted(missing))
            )

        queue = TicketQueue.objects.filter(
            ten_queue="M3 - Tiếp nhận và xử lý Ticket",
            dang_hoat_dong=True,
        ).first()

        if queue is None:
            raise CommandError(
                "Không tìm thấy Queue M3 đang hoạt động. "
                "Hãy chạy seed_m3_sla trước."
            )

        created_count = 0
        skipped_count = 0

        for (
            username,
            category_name,
            state,
            priority,
            score,
            title,
            description,
            resolution,
        ) in SCENARIOS:

            customer = customers[username]

            category = TicketCategory.objects.filter(
                ten_danh_muc=category_name,
                dang_hoat_dong=True,
            ).first()

            if category is None:
                raise CommandError(
                    f"Không tìm thấy danh mục: {category_name}"
                )

            mapping = TicketCategoryQueue.objects.filter(
                danh_muc=category,
                queue=queue,
            ).exists()

            if not mapping:
                raise CommandError(
                    f"Danh mục {category_name} chưa được "
                    "liên kết với Queue M3."
                )

            sla = SLAConfig.objects.filter(
                danh_muc=category,
                muc_uu_tien=priority,
                dang_hoat_dong=True,
            ).first()

            if sla is None:
                raise CommandError(
                    f"Thiếu SLA cho {category_name} - {priority}"
                )

            # Không tạo trùng theo khách hàng, tiêu đề
            # và nội dung nghiệp vụ.
            existing = Ticket.objects.filter(
                khach_hang=customer,
                tieu_de=title,
            ).first()

            if existing:
                self.stdout.write(
                    f"Bỏ qua Ticket đã tồn tại: {existing.ma_ticket}"
                )
                skipped_count += 1
                continue

            now = timezone.now()

            # Sinh mã Ticket theo định dạng hệ thống.
            ticket_code = (
                f"TK{now.strftime('%Y%m%d')}"
                f"{Ticket.objects.count() + created_count + 1:06d}"
            )

            while Ticket.objects.filter(
                ma_ticket=ticket_code
            ).exists():
                created_count += 1
                ticket_code = (
                    f"TK{now.strftime('%Y%m%d')}"
                    f"{Ticket.objects.count() + created_count + 1:06d}"
                )

            ticket = Ticket(
                ma_ticket=ticket_code,
                khach_hang=customer,
                tieu_de=title,
                noi_dung=description,
                danh_muc=category,
                muc_uu_tien=priority,
                trang_thai=state,
                queue=queue,
                nguoi_phu_trach=staff,
                sla_config=sla,
                sla_deadline=now + timezone.timedelta(
                    hours=sla.thoi_han_gio
                ),
                ket_qua_xu_ly=resolution,
                trang_thai_xac_nhan=(
                    "AGREED" if state == "CLOSED"
                    else "DISAGREED" if state == "REOPENED"
                    else "PENDING"
                ),
                thoi_diem_xac_nhan=(
                    now if state in ["CLOSED", "REOPENED"]
                    else None
                ),
                ly_do_khong_dong_y=(
                    "Khách hàng đề nghị xem xét lại "
                    "kết quả xử lý trước đó."
                    if state == "REOPENED"
                    else ""
                ),
            )

            ticket.full_clean()
            ticket.save()

            TicketLog.objects.create(
                ticket=ticket,
                nguoi_thuc_hien=customer.ma_tai_khoan,
                hanh_dong="TẠO YÊU CẦU HỖ TRỢ",
                noi_dung=(
                    f"Khách hàng gửi yêu cầu: {title}."
                ),
            )

            TicketLog.objects.create(
                ticket=ticket,
                nguoi_thuc_hien=staff.ma_tai_khoan,
                hanh_dong="TIẾP NHẬN TICKET",
                noi_dung=(
                    f"Nhân viên {staff.ho_ten} tiếp nhận "
                    "và phụ trách xử lý yêu cầu."
                ),
            )

            if state in ["RESOLVED", "CLOSED"]:
                TicketLog.objects.create(
                    ticket=ticket,
                    nguoi_thuc_hien=staff.ma_tai_khoan,
                    hanh_dong="CẬP NHẬT KẾT QUẢ XỬ LÝ",
                    noi_dung=resolution,
                )

            if state == "CLOSED":
                TicketLog.objects.create(
                    ticket=ticket,
                    nguoi_thuc_hien=customer.ma_tai_khoan,
                    hanh_dong="KHÁCH HÀNG XÁC NHẬN KẾT QUẢ",
                    noi_dung=(
                        "Khách hàng đồng ý kết quả xử lý."
                    ),
                )

            if state == "REOPENED":
                TicketLog.objects.create(
                    ticket=ticket,
                    nguoi_thuc_hien=customer.ma_tai_khoan,
                    hanh_dong="KHÁCH HÀNG YÊU CẦU MỞ LẠI",
                    noi_dung=(
                        "Khách hàng không đồng ý kết quả "
                        "và yêu cầu tiếp tục xem xét."
                    ),
                )

            if score is not None:
                csat = CSAT(
                    ticket=ticket,
                    score=score,
                    comment=(
                        "Khách hàng đánh giá trải nghiệm "
                        "hỗ trợ sau khi xử lý yêu cầu."
                    ),
                )
                csat.full_clean()
                csat.save()

            created_count += 1

            self.stdout.write(
                f"{ticket_code} | {customer.ho_ten} | "
                f"{category_name} | {state}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Hoàn tất: tạo {created_count} Ticket mới, "
                f"bỏ qua {skipped_count} Ticket đã tồn tại."
            )
        )
