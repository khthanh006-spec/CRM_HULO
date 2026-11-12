"""Bo sung ChatRule cho CRM HULO: don hang, giao hang, doi hang, thanh toan.

Chay tai thu muc goc Django: python bo_sung_chatrules.py
Chay lai an toan: cap nhat quy tac trung tu_khoa, khong tao ban ghi lap.
Khong sua code Chatbot, khong xoa cac quy tac hien co.
"""

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction
from chatbot.models import ChatRule

RULES = [{'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'đơn hàng',
  'thu_tu_uu_tien': 45,
  'cau_tra_loi': 'Bạn cần hỗ trợ về đơn hàng? Vui lòng cho biết mã đơn hàng và vấn đề cụ thể (kiểm tra trạng '
                 'thái, thay đổi thông tin, hủy đơn hoặc nhận sai hàng). Bạn có thể xem đơn hàng trong tài '
                 'khoản. Nếu cần kiểm tra hoặc điều chỉnh, hãy chọn **Cần nhân viên hỗ trợ**; Chatbot không '
                 'tự thay đổi đơn hàng.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'kiểm tra đơn hàng',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Để kiểm tra đơn hàng, hãy mở mục đơn hàng trong tài khoản và chọn đơn cần xem. Nếu không '
                 'tìm thấy hoặc trạng thái chưa rõ, hãy chọn **Cần nhân viên hỗ trợ** và cung cấp mã đơn '
                 'hàng để nhân viên đối chiếu.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'tra cứu đơn hàng',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Bạn có thể xem các đơn hàng thuộc tài khoản của mình trong mục đơn hàng. Nếu chưa tìm thấy '
                 'đơn, hãy gửi mã đơn hàng qua **Cần nhân viên hỗ trợ** để được kiểm tra.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'trạng thái đơn hàng',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Trạng thái đơn hàng được cập nhật trong phần quản lý đơn hàng. Nếu thấy trạng thái bất '
                 'thường hoặc chưa cập nhật, vui lòng cung cấp mã đơn hàng và chọn **Cần nhân viên hỗ trợ**.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'hủy đơn',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Nếu muốn hủy đơn hàng, bạn hãy cung cấp mã đơn và lý do hủy qua **Cần nhân viên hỗ trợ**. '
                 'Nhân viên sẽ kiểm tra trạng thái xử lý và khả năng hủy; Chatbot không thể tự xác nhận hủy '
                 'đơn.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'đổi địa chỉ',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Để yêu cầu thay đổi địa chỉ nhận hàng, vui lòng cung cấp mã đơn hàng và địa chỉ mới qua '
                 '**Cần nhân viên hỗ trợ**. Khả năng thay đổi phụ thuộc vào tình trạng xử lý và vận chuyển '
                 'của đơn.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'sai đơn hàng',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Nếu thông tin đơn hàng không đúng, hãy chuẩn bị mã đơn hàng, nội dung bị sai và ảnh chụp '
                 'thông tin đơn (nếu có). Chọn **Cần nhân viên hỗ trợ** để được đối chiếu và xử lý.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'thiếu hàng',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Nếu nhận thiếu sản phẩm trong đơn, hãy chuẩn bị mã đơn, danh sách sản phẩm còn thiếu và '
                 'ảnh kiện hàng nếu có. Chọn **Cần nhân viên hỗ trợ** để gửi yêu cầu kiểm tra.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'giao hàng',
  'thu_tu_uu_tien': 45,
  'cau_tra_loi': 'Bạn cần hỗ trợ giao hàng? Vui lòng cho biết mã đơn hàng và vấn đề gặp phải, chẳng hạn giao '
                 'chậm, chưa nhận được hàng, sai địa chỉ hoặc giao không thành công. Hãy kiểm tra trạng thái '
                 'đơn trong tài khoản hoặc chọn **Cần nhân viên hỗ trợ** để nhân viên tra cứu.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'vận chuyển',
  'thu_tu_uu_tien': 45,
  'cau_tra_loi': 'Bạn có thể kiểm tra tiến độ vận chuyển trong thông tin đơn hàng. Nếu đơn chậm cập nhật, '
                 'thất lạc hoặc không giao được, hãy chọn **Cần nhân viên hỗ trợ** và cung cấp mã đơn hàng.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'ship',
  'thu_tu_uu_tien': 45,
  'cau_tra_loi': 'Bạn muốn hỏi về vận chuyển hoặc giao hàng? Hãy cho biết mã đơn và vấn đề cụ thể. Thông tin '
                 'phí và tiến độ giao phải được kiểm tra theo đơn thực tế; chọn **Cần nhân viên hỗ trợ** nếu '
                 'cần nhân viên đối chiếu.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'giao hàng chậm',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Nếu đơn giao chậm, hãy kiểm tra trạng thái trong tài khoản và chuẩn bị mã đơn cùng thời '
                 'gian dự kiến nhận hàng (nếu có). Chọn **Cần nhân viên hỗ trợ** để nhân viên kiểm tra '
                 'nguyên nhân và phản hồi.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'chưa nhận được hàng',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Nếu chưa nhận được hàng, vui lòng kiểm tra trạng thái đơn, số điện thoại nhận hàng và mã '
                 'đơn. Nếu hệ thống báo đã giao nhưng bạn chưa nhận, hãy chọn **Cần nhân viên hỗ trợ** để '
                 'kiểm tra với bộ phận liên quan.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'giao không thành công',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Khi đơn giao không thành công, bạn hãy kiểm tra thông tin liên hệ và địa chỉ nhận hàng. '
                 'Chọn **Cần nhân viên hỗ trợ** và cung cấp mã đơn để nhân viên xem xét phương án giao lại '
                 'hoặc xử lý tiếp theo.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'giao sai địa chỉ',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Nếu đơn đang được giao tới sai địa chỉ, hãy cung cấp mã đơn và địa chỉ nhận chính xác qua '
                 '**Cần nhân viên hỗ trợ** càng sớm càng tốt. Việc điều chỉnh phụ thuộc vào tình trạng vận '
                 'chuyển.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'phí vận chuyển',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Phí vận chuyển cần được xác định theo đơn hàng, địa chỉ nhận và phương thức giao cụ thể. '
                 'Bạn hãy kiểm tra thông tin phí của đơn; nếu thấy chênh lệch, chọn **Cần nhân viên hỗ trợ** '
                 'để được đối chiếu.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'mã vận đơn',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Mã vận đơn (nếu đã được cung cấp) giúp theo dõi tình trạng giao hàng. Nếu bạn chưa thấy mã '
                 'hoặc không tra cứu được, hãy chọn **Cần nhân viên hỗ trợ** và cung cấp mã đơn hàng.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'đổi hàng',
  'thu_tu_uu_tien': 55,
  'cau_tra_loi': 'Nếu muốn đổi hàng, bạn hãy chuẩn bị mã đơn hàng, tên sản phẩm, lý do đổi và ảnh tình trạng '
                 'sản phẩm nếu có. Chọn **Cần nhân viên hỗ trợ**; nhân viên sẽ kiểm tra điều kiện và hướng '
                 'dẫn quy trình đổi hàng theo chính sách áp dụng.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'trả hàng',
  'thu_tu_uu_tien': 55,
  'cau_tra_loi': 'Để đề nghị trả hàng, vui lòng cung cấp mã đơn, sản phẩm cần trả, lý do và hình ảnh minh '
                 'chứng nếu có. Chọn **Cần nhân viên hỗ trợ** để được kiểm tra điều kiện và hướng dẫn các '
                 'bước tiếp theo.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'hoàn tiền',
  'thu_tu_uu_tien': 60,
  'cau_tra_loi': 'Nếu bạn muốn đề nghị hoàn tiền, hãy cung cấp mã đơn, sản phẩm hoặc khoản thanh toán liên '
                 'quan, lý do và minh chứng nếu có. Chọn **Cần nhân viên hỗ trợ** để nhân viên xác minh và '
                 'xem xét phương án hoàn tiền. Chatbot không thể tự duyệt hoặc thực hiện chuyển tiền.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'đổi sản phẩm',
  'thu_tu_uu_tien': 60,
  'cau_tra_loi': 'Để yêu cầu đổi sản phẩm, hãy chuẩn bị mã đơn, tên sản phẩm, tình trạng thực tế và lý do '
                 'đổi. Chọn **Cần nhân viên hỗ trợ** để được kiểm tra điều kiện đổi và phương án phù hợp.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'đổi nhầm hàng',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Nếu nhận nhầm sản phẩm, hãy giữ lại sản phẩm và bao bì, chụp ảnh sản phẩm nhận được cùng '
                 'thông tin đơn hàng. Chọn **Cần nhân viên hỗ trợ** để nhân viên đối chiếu và hướng dẫn xử '
                 'lý.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'đổi hàng bị lỗi',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Nếu hàng bị lỗi và bạn muốn đổi, hãy cung cấp mã đơn, mô tả lỗi và hình ảnh sản phẩm. Chọn '
                 '**Cần nhân viên hỗ trợ** để được kiểm tra điều kiện đổi hoặc bảo hành.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'quy trình đổi trả',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Quy trình đổi trả thường bắt đầu bằng việc gửi yêu cầu, cung cấp mã đơn và lý do kèm minh '
                 'chứng, sau đó nhân viên kiểm tra điều kiện và thông báo hướng xử lý. Chọn **Cần nhân viên '
                 'hỗ trợ** để được hướng dẫn theo chính sách của đơn hàng cụ thể.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'thanh toán đơn hàng',
  'thu_tu_uu_tien': 55,
  'cau_tra_loi': 'Bạn có thể kiểm tra phương thức và thông tin thanh toán trong đơn hàng của mình. Nếu gặp '
                 'lỗi thanh toán hoặc có khoản phí chưa rõ, hãy cung cấp mã đơn và mô tả sự cố qua **Cần '
                 'nhân viên hỗ trợ**. Không gửi OTP, mật khẩu hoặc thông tin thẻ đầy đủ.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'thanh toán thất bại',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Nếu thanh toán thất bại, hãy kiểm tra thông báo lỗi, kết nối và trạng thái giao dịch trong '
                 'ứng dụng ngân hàng hoặc phương thức thanh toán của bạn. Tránh thanh toán lại nhiều lần khi '
                 'chưa rõ giao dịch trước đã thành công hay chưa. Chọn **Cần nhân viên hỗ trợ** và cung cấp '
                 'mã đơn cùng thời điểm giao dịch; không cung cấp OTP.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'bị trừ tiền',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Nếu tài khoản đã bị trừ tiền nhưng đơn chưa ghi nhận thanh toán, hãy lưu thông báo giao '
                 'dịch và mã đơn. Chọn **Cần nhân viên hỗ trợ** để nhân viên đối chiếu; không gửi thông tin '
                 'thẻ đầy đủ, mật khẩu hoặc OTP.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'thanh toán hai lần',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Nếu nghi ngờ thanh toán trùng hai lần, hãy lưu mã đơn, thời điểm và mã tham chiếu giao '
                 'dịch (nếu có). Chọn **Cần nhân viên hỗ trợ** để được xác minh và hướng dẫn xử lý khoản '
                 'tiền liên quan.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'chuyển khoản',
  'thu_tu_uu_tien': 60,
  'cau_tra_loi': 'Nếu thanh toán bằng chuyển khoản, hãy thực hiện theo thông tin thanh toán chính thức hiển '
                 'thị trong đơn hoặc hướng dẫn xác minh của cửa hàng. Khi cần đối chiếu, hãy cung cấp mã đơn '
                 'và mã giao dịch qua **Cần nhân viên hỗ trợ**; không gửi mật khẩu hay OTP.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'cod',
  'thu_tu_uu_tien': 60,
  'cau_tra_loi': 'Bạn muốn hỏi về thanh toán khi nhận hàng (COD)? Vui lòng kiểm tra phương thức thanh toán '
                 'được hiển thị trong đơn hàng. Nếu muốn thay đổi hoặc xác minh COD có được hỗ trợ hay '
                 'không, chọn **Cần nhân viên hỗ trợ**.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'hóa đơn',
  'thu_tu_uu_tien': 60,
  'cau_tra_loi': 'Nếu cần kiểm tra hoặc đề nghị xuất hóa đơn, hãy cung cấp mã đơn và thông tin cần xuất hóa '
                 'đơn qua **Cần nhân viên hỗ trợ**. Nhân viên sẽ kiểm tra chứng từ và hướng dẫn theo quy '
                 'trình áp dụng.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'phương thức thanh toán',
  'thu_tu_uu_tien': 60,
  'cau_tra_loi': 'Các phương thức thanh toán khả dụng phụ thuộc vào cấu hình của đơn hàng. Hãy kiểm tra lựa '
                 'chọn hiển thị khi đặt hàng; nếu không thấy phương thức mong muốn, chọn **Cần nhân viên hỗ '
                 'trợ** để được tư vấn.',
  'dang_hoat_dong': True}]

def main():
    created = 0
    updated = 0
    with transaction.atomic():
        for rule in RULES:
            keyword = rule["tu_khoa"]
            defaults = {k: v for k, v in rule.items() if k != "tu_khoa"}
            obj, was_created = ChatRule.objects.update_or_create(
                tu_khoa=keyword, defaults=defaults
            )
            created += int(was_created)
            updated += int(not was_created)
    print(f"Hoan tat: tao moi {created} quy tac; cap nhat {updated} quy tac.")
    print(f"Tong quy tac hien tai: {ChatRule.objects.count()}")

if __name__ == "__main__":
    main()
