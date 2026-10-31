
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import Staff
from customers.models import Customer
from tickets.models import Ticket, TicketLog


User = get_user_model()


class UC35ReopenedTest(TestCase):

    def setUp(self):
        # 1. Tạo tài khoản khách hàng
        self.customer_user = User.objects.create_user(
            username='test_uc35_customer',
            password='TestPassword123!'
        )

        self.customer = Customer.objects.create(
            ma_tai_khoan=self.customer_user,
            ho_ten='Khách hàng kiểm thử',
            email='uc35_customer@example.com'
        )

        # 2. Tạo nhân viên CSKH ban đầu
        self.staff_user = User.objects.create_user(
            username='test_uc35_staff',
            password='TestPassword123!'
        )

        self.staff = Staff.objects.create(
            ma_tai_khoan=self.staff_user,
            ho_ten='Nhân viên CSKH A',
            email='uc35_staff@example.com',
            vai_tro='CSKH'
        )

        # 3. Tạo Ticket đang chờ khách hàng xác nhận
        self.ticket = Ticket.objects.create(
            ma_ticket='TEST_UC35_001',
            khach_hang=self.customer,
            tieu_de='Kiểm thử mở lại Ticket',
            noi_dung='Khách hàng phản ánh sản phẩm bị lỗi.',
            trang_thai='RESOLVED',
            trang_thai_xac_nhan='PENDING',
            nguoi_phu_trach=self.staff
        )

    def test_customer_disagree_keeps_ticket_and_staff(self):
        """
        Khách hàng không đồng ý:
        - Ticket chuyển RESOLVED -> REOPENED
        - Giữ nguyên mã Ticket
        - Giữ nguyên nhân viên CSKH phụ trách
        - Lưu lý do và lịch sử xử lý
        """

        original_pk = self.ticket.pk
        original_code = self.ticket.ma_ticket
        original_staff_id = self.ticket.nguoi_phu_trach_id

        # Đăng nhập bằng tài khoản khách hàng
        self.client.force_login(self.customer_user)

        # Gửi yêu cầu không đồng ý với kết quả
        response = self.client.post(
            reverse(
                'tickets:customer_confirm',
                args=[self.ticket.pk]
            ),
            {
                'lua_chon': 'DISAGREE',
                'ly_do': 'Sản phẩm vẫn chưa được xử lý đúng.'
            }
        )

        # Kiểm tra hệ thống chuyển hướng
        self.assertEqual(response.status_code, 302)

        # Lấy lại dữ liệu Ticket sau khi cập nhật
        self.ticket.refresh_from_db()

        # Kiểm tra không tạo Ticket mới
        self.assertEqual(self.ticket.pk, original_pk)

        # Kiểm tra mã Ticket không thay đổi
        self.assertEqual(self.ticket.ma_ticket, original_code)

        # Kiểm tra nhân viên phụ trách không thay đổi
        self.assertEqual(
            self.ticket.nguoi_phu_trach_id,
            original_staff_id
        )

        # Kiểm tra trạng thái REOPENED
        self.assertEqual(
            self.ticket.trang_thai,
            'REOPENED'
        )

        # Kiểm tra trạng thái xác nhận
        self.assertEqual(
            self.ticket.trang_thai_xac_nhan,
            'DISAGREED'
        )

        # Kiểm tra lý do không đồng ý
        self.assertEqual(
            self.ticket.ly_do_khong_dong_y,
            'Sản phẩm vẫn chưa được xử lý đúng.'
        )

        # Kiểm tra Ticket cũ vẫn tồn tại duy nhất
        self.assertEqual(
            Ticket.objects.filter(pk=original_pk).count(),
            1
        )

        # Kiểm tra hệ thống ghi lịch sử xử lý
        self.assertTrue(
            TicketLog.objects.filter(
                ticket=self.ticket,
                hanh_dong='KHÁCH HÀNG YÊU CẦU MỞ LẠI'
            ).exists()
        )


    def test_assigned_staff_can_resume_reopened_ticket(self):
        """
        Nhân viên CSKH được phân công có thể tiếp tục
        xử lý Ticket REOPENED, giữ nguyên người phụ trách.
        """

        self.ticket.trang_thai = 'REOPENED'
        self.ticket.trang_thai_xac_nhan = 'DISAGREED'
        self.ticket.save()

        original_code = self.ticket.ma_ticket
        original_staff_id = self.ticket.nguoi_phu_trach_id

        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse('tickets:resume', args=[self.ticket.pk])
        )

        self.assertEqual(response.status_code, 302)

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.trang_thai,
            'IN_PROGRESS'
        )
        self.assertEqual(self.ticket.ma_ticket, original_code)
        self.assertEqual(
            self.ticket.nguoi_phu_trach_id,
            original_staff_id
        )

        self.assertTrue(
            TicketLog.objects.filter(
                ticket=self.ticket,
                hanh_dong='TIẾP TỤC XỬ LÝ'
            ).exists()
        )


    def test_other_staff_cannot_resume_reopened_ticket(self):
        """
        Nhân viên CSKH khác không được tiếp tục
        xử lý Ticket đã phân công cho CSKH ban đầu.
        """

        # Tạo tài khoản CSKH thứ hai
        other_user = User.objects.create_user(
            username='test_uc35_other_staff',
            password='TestPassword123!'
        )

        other_staff = Staff.objects.create(
            ma_tai_khoan=other_user,
            ho_ten='Nhân viên CSKH B',
            email='uc35_other_staff@example.com',
            vai_tro='CSKH'
        )

        # Chuẩn bị Ticket ở trạng thái REOPENED
        self.ticket.trang_thai = 'REOPENED'
        self.ticket.save()

        original_staff_id = self.ticket.nguoi_phu_trach_id

        # Đăng nhập bằng nhân viên B
        self.client.force_login(other_user)

        response = self.client.post(
            reverse('tickets:resume', args=[self.ticket.pk])
        )

        # Nhân viên B phải bị từ chối
        self.assertEqual(response.status_code, 403)

        self.ticket.refresh_from_db()

        # Ticket vẫn REOPENED
        self.assertEqual(
            self.ticket.trang_thai,
            'REOPENED'
        )

        # Vẫn thuộc nhân viên A
        self.assertEqual(
            self.ticket.nguoi_phu_trach_id,
            original_staff_id
        )

        # Không được ghi log tiếp tục xử lý
        self.assertFalse(
            TicketLog.objects.filter(
                ticket=self.ticket,
                hanh_dong='TIẾP TỤC XỬ LÝ'
            ).exists()
        )


    def test_customer_disagree_without_reason_is_rejected(self):
        """
        Khách hàng không đồng ý nhưng không nhập lý do:
        - Không mở lại Ticket
        - Giữ trạng thái RESOLVED
        - Không tạo log mở lại
        """

        self.client.force_login(self.customer_user)

        response = self.client.post(
            reverse(
                'tickets:customer_confirm',
                args=[self.ticket.pk]
            ),
            {
                'lua_chon': 'DISAGREE',
                'ly_do': ''
            }
        )

        self.assertEqual(response.status_code, 302)

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.trang_thai,
            'RESOLVED'
        )

        self.assertEqual(
            self.ticket.trang_thai_xac_nhan,
            'PENDING'
        )

        self.assertFalse(
            TicketLog.objects.filter(
                ticket=self.ticket,
                hanh_dong='KHÁCH HÀNG YÊU CẦU MỞ LẠI'
            ).exists()
        )


    def test_customer_cannot_confirm_twice(self):
        """
        Khách hàng không thể xác nhận kết quả hai lần.
        Lần xác nhận thứ hai không được thay đổi Ticket
        hoặc tạo thêm TicketLog.
        """

        self.client.force_login(self.customer_user)

        url = reverse(
            'tickets:customer_confirm',
            args=[self.ticket.pk]
        )

        # Lần 1: Khách hàng đồng ý
        first_response = self.client.post(
            url,
            {
                'lua_chon': 'AGREE',
                'ly_do': ''
            }
        )

        self.assertEqual(first_response.status_code, 302)

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.trang_thai_xac_nhan,
            'AGREED'
        )

        # Đếm số log sau lần xác nhận đầu tiên
        first_log_count = TicketLog.objects.filter(
            ticket=self.ticket,
            hanh_dong='KHÁCH HÀNG ĐỒNG Ý'
        ).count()

        self.assertEqual(first_log_count, 1)

        # Lần 2: Gửi lại yêu cầu xác nhận
        second_response = self.client.post(
            url,
            {
                'lua_chon': 'AGREE',
                'ly_do': ''
            }
        )

        self.assertEqual(second_response.status_code, 302)

        self.ticket.refresh_from_db()

        # Ticket không bị thay đổi xác nhận
        self.assertEqual(
            self.ticket.trang_thai_xac_nhan,
            'AGREED'
        )

        self.assertEqual(
            self.ticket.trang_thai,
            'RESOLVED'
        )

        # Không tạo thêm log xác nhận
        self.assertEqual(
            TicketLog.objects.filter(
                ticket=self.ticket,
                hanh_dong='KHÁCH HÀNG ĐỒNG Ý'
            ).count(),
            1
        )


