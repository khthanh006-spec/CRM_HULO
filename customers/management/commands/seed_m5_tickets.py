from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Staff
from customers.models import Customer, CSAT
from tickets.models import (
    Ticket,
    TicketCategory,
    TicketQueue,
    TicketLog,
)


DEMO_MARKER = '[DEMO M5 TICKETS V1]'


# Mã, khách hàng demo, trạng thái, ưu tiên, CSAT, tiêu đề
SCENARIOS = [
    (
        'M5_DEMO_TK_01', 'm5_demo_01',
        'NEW', 'LOW', None,
        'Cần hướng dẫn bảo quản áo in',
    ),
    (
        'M5_DEMO_TK_02', 'm5_demo_02',
        'ASSIGNED', 'MEDIUM', None,
        'Cần kiểm tra tiến độ giao hàng',
    ),
    (
        'M5_DEMO_TK_03', 'm5_demo_03',
        'IN_PROGRESS', 'HIGH', None,
        'Màu bản in khác với mẫu đã xác nhận',
    ),
    (
        'M5_DEMO_TK_04', 'm5_demo_04',
        'RESOLVED_PENDING', 'MEDIUM', None,
        'Đã hướng dẫn khắc phục lỗi bảo quản',
    ),
    (
        'M5_DEMO_TK_05', 'm5_demo_05',
        'RESOLVED_AGREED', 'MEDIUM', None,
        'Khách đồng ý kết quả và chưa đánh giá',
    ),
    (
        'M5_DEMO_TK_06', 'm5_demo_06',
        'CLOSED', 'HIGH', 1,
        'Khách chưa hài lòng về trải nghiệm hỗ trợ',
    ),
    (
        'M5_DEMO_TK_07', 'm5_demo_07',
        'CLOSED', 'HIGH', 2,
        'Khách phản hồi thời gian xử lý quá lâu',
    ),
    (
        'M5_DEMO_TK_08', 'm5_demo_08',
        'CLOSED', 'MEDIUM', 3,
        'Khách đánh giá hỗ trợ ở mức trung bình',
    ),
    (
        'M5_DEMO_TK_09', 'm5_demo_09',
        'CLOSED', 'LOW', 4,
        'Khách hài lòng với hướng dẫn sử dụng',
    ),
    (
        'M5_DEMO_TK_10', 'm5_demo_10',
        'CLOSED', 'LOW', 5,
        'Khách rất hài lòng với hỗ trợ sau mua',
    ),
    (
        'M5_DEMO_TK_11', 'm5_demo_01',
        'REOPENED', 'URGENT', None,
        'Khách yêu cầu kiểm tra lại lỗi bản in',
    ),
    (
        'M5_DEMO_TK_12', 'm5_demo_02',
        'RESUMED', 'HIGH', None,
        'Đang tiếp tục xử lý sau khi mở lại',
    ),
]


CSAT_COMMENTS = {
    1: 'Vấn đề đã xử lý nhưng trải nghiệm hỗ trợ chưa tốt.',
    2: 'Đã nhận kết quả nhưng thời gian chờ còn lâu.',
    3: 'Hỗ trợ ở mức trung bình, cần giải thích rõ hơn.',
    4: 'Hướng dẫn rõ ràng, nhân viên hỗ trợ tốt.',
    5: 'Rất hài lòng, nhân viên hỗ trợ nhanh và tận tình.',
}


class Command(BaseCommand):
    help = (
        'Bổ sung Ticket, lịch sử và CSAT demo '
        'cho khách hàng mẫu M5.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--staff',
            default='cskh01',
            help='Username nhân viên CSKH phụ trách Ticket demo.',
        )

    def handle(self, *args, **options):
        staff = (
            Staff.objects
            .select_related('ma_tai_khoan')
            .filter(
                ma_tai_khoan__username=options['staff'],
                ma_tai_khoan__is_active=True,
                vai_tro='CSKH',
            )
            .first()
        )

        if staff is None:
            raise CommandError(
                'Không tìm thấy nhân viên CSKH đang hoạt động. '
                'Chạy lại với --staff username_cskh.'
            )

        usernames = {
            scenario[1]
            for scenario in SCENARIOS
        }

        customers = {
            customer.ma_tai_khoan.username: customer
            for customer in (
                Customer.objects
                .select_related('ma_tai_khoan')
                .filter(
                    ma_tai_khoan__username__in=usernames,
                )
            )
        }

        missing = sorted(usernames - set(customers))

        if missing:
            raise CommandError(
                'Thiếu khách hàng demo: '
                + ', '.join(missing)
                + '. Hãy chạy seed_m5_customers trước.'
            )

        # Kiểm tra mã trùng trước khi ghi dữ liệu.
        pending = []

        for scenario in SCENARIOS:
            code, username, state, priority, score, title = scenario

            existing = Ticket.objects.filter(
                ma_ticket=code,
            ).first()

            if existing:
                if (
                    existing.khach_hang_id
                    != customers[username].pk
                    or not existing.noi_dung.startswith(DEMO_MARKER)
                ):
                    raise CommandError(
                        f'Mã {code} đã được sử dụng '
                        'bởi dữ liệu khác. Không ghi đè.'
                    )

                self.stdout.write(
                    f'Bỏ qua Ticket đã có: {code}'
                )
                continue

            pending.append(scenario)

        if not pending:
            self.stdout.write(
                self.style.SUCCESS(
                    'Bộ Ticket demo đã tồn tại. '
                    'Không thay đổi dữ liệu.'
                )
            )
            return

        created_codes = []

        with transaction.atomic():
            category, _ = TicketCategory.objects.get_or_create(
                ten_danh_muc='DEMO M5 - Hỗ trợ sau mua',
                defaults={
                    'mo_ta': 'Danh mục dữ liệu giả lập phục vụ M5.',
                    'dang_hoat_dong': True,
                },
            )

            queue, _ = TicketQueue.objects.get_or_create(
                ten_queue='DEMO M5 - Chăm sóc khách hàng',
                defaults={
                    'mo_ta': 'Hàng đợi dữ liệu giả lập phục vụ M5.',
                    'dang_hoat_dong': True,
                },
            )

            if not category.dang_hoat_dong or not queue.dang_hoat_dong:
                raise CommandError(
                    'Danh mục hoặc hàng đợi demo đã bị tạm dừng. '
                    'Lệnh không tự bật lại.'
                )

            for scenario in pending:
                code, username, state, priority, score, title = scenario

                customer = customers[username]

                if state in [
                    'RESOLVED_PENDING',
                    'RESOLVED_AGREED',
                ]:
                    status = 'RESOLVED'
                elif state == 'RESUMED':
                    status = 'IN_PROGRESS'
                else:
                    status = state

                agreed = state in [
                    'RESOLVED_AGREED',
                    'CLOSED',
                ]

                reopened = state in [
                    'REOPENED',
                    'RESUMED',
                ]

                confirmation = (
                    'AGREED'
                    if agreed
                    else 'DISAGREED'
                    if reopened
                    else 'PENDING'
                )

                has_result = (
                    status in ['RESOLVED', 'CLOSED']
                    or reopened
                )

                ticket = Ticket(
                    ma_ticket=code,
                    khach_hang=customer,
                    tieu_de=title,
                    noi_dung=(
                        f'{DEMO_MARKER}\n'
                        f'{title}.\n'
                        'Tình huống giả lập để kiểm tra '
                        'Customer 360°, CSAT và hậu mãi. '
                        'Không phải yêu cầu thực tế.'
                    ),
                    danh_muc=category,
                    muc_uu_tien=priority,
                    trang_thai=status,
                    queue=queue if status != 'NEW' else None,
                    nguoi_phu_trach=(
                        staff if status != 'NEW' else None
                    ),
                    trang_thai_xac_nhan=confirmation,
                    thoi_diem_xac_nhan=(
                        timezone.now()
                        if agreed or reopened
                        else None
                    ),
                    ly_do_khong_dong_y=(
                        'DEMO: khách yêu cầu kiểm tra lại '
                        'vì kết quả chưa đáp ứng mong đợi.'
                        if reopened
                        else ''
                    ),
                    ket_qua_xu_ly=(
                        'DEMO: đã kiểm tra và cung cấp '
                        'hướng xử lý cho khách hàng.'
                        if has_result
                        else ''
                    ),
                )

                ticket.full_clean()
                ticket.save()

                def add_log(action, content, actor):
                    return TicketLog.objects.create(
                        ticket=ticket,
                        nguoi_thuc_hien=actor,
                        hanh_dong=action,
                        noi_dung=f'{DEMO_MARKER} {content}',
                    )

                add_log(
                    'TẠO TICKET DEMO M5',
                    'Khởi tạo tình huống giả lập.',
                    customer.ma_tai_khoan,
                )

                if status != 'NEW':
                    add_log(
                        'TIẾP NHẬN TICKET',
                        f'Phân công cho {staff.ho_ten}.',
                        staff.ma_tai_khoan,
                    )

                if has_result:
                    add_log(
                        'HOÀN TẤT XỬ LÝ',
                        'Đã cung cấp kết quả xử lý giả lập.',
                        staff.ma_tai_khoan,
                    )

                if agreed:
                    add_log(
                        'KHÁCH HÀNG ĐỒNG Ý',
                        'Khách đồng ý kết quả xử lý giả lập.',
                        customer.ma_tai_khoan,
                    )

                if state == 'CLOSED':
                    add_log(
                        'ĐÓNG TICKET DEMO M5',
                        'Đóng Ticket sau khi khách đồng ý.',
                        staff.ma_tai_khoan,
                    )

                if reopened:
                    add_log(
                        'KHÁCH HÀNG YÊU CẦU MỞ LẠI',
                        'Khách không đồng ý kết quả. '
                        'Trạng thái RESOLVED → REOPENED.',
                        customer.ma_tai_khoan,
                    )

                if state == 'RESUMED':
                    add_log(
                        'TIẾP TỤC XỬ LÝ',
                        'Trạng thái REOPENED → IN_PROGRESS.',
                        staff.ma_tai_khoan,
                    )

                if score is not None:
                    csat = CSAT(
                        ticket=ticket,
                        score=score,
                        comment=(
                            'DEMO: '
                            + CSAT_COMMENTS[score]
                        ),
                    )

                    csat.full_clean()
                    csat.save()

                created_codes.append(
                    (
                        code,
                        customer.ho_ten,
                        status,
                        score,
                    )
                )

        for code, name, status, score in created_codes:
            rating = (
                f'{score}/5'
                if score is not None
                else 'Chưa đánh giá'
            )

            self.stdout.write(
                f'{code} | {name} | {status} | {rating}'
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Đã tạo {len(created_codes)} Ticket demo. '
                'Dữ liệu có sẵn được giữ nguyên.'
            )
        )