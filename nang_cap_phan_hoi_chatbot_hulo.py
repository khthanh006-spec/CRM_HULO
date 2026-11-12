"""Nâng cấp nội dung tư vấn cho 32 ChatRule bổ sung của HULO CRM.

Chạy ở thư mục gốc dự án: python nang_cap_phan_hoi_chatbot_hulo.py
Chỉ cập nhật 32 từ khóa mới và 3 từ khóa cũ liên quan; không tạo hay xóa rule.
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
  'cau_tra_loi': 'Mình sẽ giúp bạn xác định đúng vấn đề với đơn hàng nhé.\n'
                 '\n'
                 '• Muốn biết đơn đang ở đâu: mở **Đơn hàng của tôi** và xem trạng thái/mã đơn.\n'
                 '• Muốn sửa thông tin hoặc hủy đơn: nên gửi yêu cầu sớm, trước khi đơn được bàn giao vận '
                 'chuyển.\n'
                 '• Nhận thiếu hoặc sai sản phẩm: giữ lại bao bì và chụp ảnh hàng đã nhận.\n'
                 '\n'
                 'Bạn đang muốn **tra cứu, hủy, chỉnh thông tin hay khiếu nại đơn**? Nếu cần kiểm tra đơn cụ '
                 'thể, chọn **Cần nhân viên hỗ trợ** và cung cấp mã đơn. Chatbot chưa thể tự thay đổi đơn '
                 'hàng.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'kiểm tra đơn hàng',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Để kiểm tra đơn hàng, bạn hãy đăng nhập và mở mục **Đơn hàng của tôi** để xem thông tin '
                 'đơn cùng trạng thái xử lý.\n'
                 '\n'
                 'Nếu không thấy đơn, hãy kiểm tra xem bạn có đăng nhập đúng tài khoản đặt hàng không. Nếu '
                 'trạng thái chưa cập nhật hoặc khác với thực tế, chọn **Cần nhân viên hỗ trợ**, gửi mã đơn '
                 'và mô tả điểm bất thường. Nhân viên sẽ đối chiếu dữ liệu trên hệ thống trước khi phản hồi.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'tra cứu đơn hàng',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Bạn có thể tra cứu đơn trong **Đơn hàng của tôi** sau khi đăng nhập tài khoản đã dùng khi '
                 'đặt hàng.\n'
                 '\n'
                 'Nếu đơn chưa hiển thị, đừng vội đặt lại: trước tiên kiểm tra thông báo xác nhận đặt hàng '
                 'hoặc mã đơn đã nhận. Sau đó chọn **Cần nhân viên hỗ trợ**, cung cấp mã đơn (nếu có) và '
                 'thời điểm đặt hàng để nhân viên kiểm tra, tránh tạo đơn trùng.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'trạng thái đơn hàng',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Trạng thái đơn cho biết đơn đang được tiếp nhận, xử lý hay đã chuyển sang giai đoạn giao '
                 'nhận. Bạn hãy mở **Đơn hàng của tôi** và xem trạng thái gần nhất.\n'
                 '\n'
                 'Nếu trạng thái đứng yên quá lâu hoặc hiển thị đã giao dù bạn chưa nhận, hãy ghi lại mã đơn '
                 'và thời điểm cập nhật cuối, sau đó chọn **Cần nhân viên hỗ trợ** để kiểm tra cụ thể. '
                 'Chatbot không tự xác nhận tình trạng vận chuyển thực tế.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'hủy đơn',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Mình hiểu bạn muốn hủy đơn và tránh phát sinh giao hàng hoặc thanh toán không cần thiết.\n'
                 '\n'
                 '**Bạn nên làm ngay:** (1) mở đơn để kiểm tra trạng thái hiện tại; (2) chuẩn bị mã đơn và '
                 'lý do hủy; (3) chọn **Cần nhân viên hỗ trợ** để gửi yêu cầu.\n'
                 '\n'
                 'Nếu đơn chưa bàn giao vận chuyển, khả năng xử lý thường thuận lợi hơn. Nếu đã vận chuyển, '
                 'nhân viên sẽ kiểm tra phương án phù hợp theo tình trạng đơn và chính sách áp dụng. **Yêu '
                 'cầu gửi đi chưa có nghĩa đơn đã được hủy.**',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'đổi địa chỉ',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Bạn muốn đổi địa chỉ nhận hàng? Hãy gửi yêu cầu càng sớm càng tốt vì đơn đã bàn giao vận '
                 'chuyển có thể khó điều chỉnh.\n'
                 '\n'
                 'Chuẩn bị **mã đơn, địa chỉ nhận mới đầy đủ, số điện thoại liên hệ**; sau đó chọn **Cần '
                 'nhân viên hỗ trợ**. Nhân viên sẽ kiểm tra trạng thái đơn và khả năng điều chỉnh với bộ '
                 'phận giao nhận. Chỉ coi địa chỉ đã thay đổi khi nhận được xác nhận.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'sai đơn hàng',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Nếu thông tin đơn không đúng, bạn vui lòng xác định phần bị sai: **sản phẩm, số lượng, '
                 'giá, địa chỉ hay người nhận**.\n'
                 '\n'
                 'Hãy mở thông tin đơn để đối chiếu, giữ lại ảnh chụp xác nhận đặt hàng (nếu có) và chọn '
                 '**Cần nhân viên hỗ trợ**. Gửi mã đơn cùng nội dung sai để nhân viên kiểm tra và hướng dẫn '
                 'cách điều chỉnh. Nếu hàng đang vận chuyển, nên báo sớm.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đơn hàng',
  'tu_khoa': 'thiếu hàng',
  'thu_tu_uu_tien': 65,
  'cau_tra_loi': 'Rất tiếc vì đơn hàng của bạn chưa đủ sản phẩm. Để xác minh nhanh và công bằng, bạn hãy:\n'
                 '\n'
                 '1. Đối chiếu số lượng thực nhận với chi tiết đơn hàng.\n'
                 '2. Giữ bao bì, tem vận chuyển và chụp ảnh sản phẩm/kiện hàng còn lại.\n'
                 '3. Chọn **Cần nhân viên hỗ trợ**, gửi mã đơn, tên và số lượng hàng thiếu cùng ảnh minh '
                 'chứng.\n'
                 '\n'
                 'Nhân viên sẽ kiểm tra thông tin đóng gói và giao nhận trước khi đề xuất phương án xử lý '
                 'phù hợp.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'giao hàng',
  'thu_tu_uu_tien': 45,
  'cau_tra_loi': 'Mình có thể hướng dẫn bạn xử lý vấn đề giao nhận. Bạn đang gặp trường hợp nào?\n'
                 '\n'
                 '• **Giao chậm:** kiểm tra ngày dự kiến nhận và trạng thái đơn.\n'
                 '• **Chưa nhận hàng:** kiểm tra lịch sử giao và số điện thoại người nhận.\n'
                 '• **Giao không thành công/sai địa chỉ:** kiểm tra thông tin giao nhận và báo sớm.\n'
                 '• **Hỏi phí hoặc mã vận đơn:** xem chi tiết đơn hàng.\n'
                 '\n'
                 'Hãy nói rõ tình huống hoặc chọn **Cần nhân viên hỗ trợ** và cung cấp mã đơn để nhân viên '
                 'đối chiếu. Chatbot chưa có dữ liệu vị trí giao hàng theo thời gian thực.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'vận chuyển',
  'thu_tu_uu_tien': 45,
  'cau_tra_loi': 'Để theo dõi vận chuyển, trước tiên bạn hãy mở đơn hàng và xem **trạng thái giao nhận, mã '
                 'vận đơn (nếu có)** cùng lần cập nhật gần nhất.\n'
                 '\n'
                 'Nếu hành trình không cập nhật, đơn bị giao trễ hoặc báo giao thành công nhưng chưa nhận, '
                 'bạn nên lưu lại màn hình trạng thái và chọn **Cần nhân viên hỗ trợ**, gửi mã đơn để được '
                 'kiểm tra với bộ phận liên quan.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'ship',
  'thu_tu_uu_tien': 45,
  'cau_tra_loi': 'Bạn đang hỏi về **phí ship, thời gian giao hay tình trạng shipper giao hàng**?\n'
                 '\n'
                 'Phí và thời gian dự kiến phụ thuộc địa chỉ, đơn hàng và phương thức giao nhận; Chatbot '
                 'chưa thể báo chính xác nếu không có dữ liệu đơn cụ thể. Bạn có thể xem thông tin trong đơn '
                 'đã đặt; nếu còn chênh lệch hoặc cần kiểm tra giao nhận, chọn **Cần nhân viên hỗ trợ** và '
                 'cung cấp mã đơn.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'giao hàng chậm',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Mình hiểu việc chờ hàng lâu hơn dự kiến gây bất tiện, nhất là khi bạn cần dùng sản phẩm '
                 'gấp.\n'
                 '\n'
                 '**Bạn hãy kiểm tra:** (1) trạng thái giao gần nhất; (2) ngày nhận dự kiến; (3) có thông '
                 'báo giao thất bại hoặc liên hệ từ đơn vị vận chuyển không.\n'
                 '\n'
                 'Nếu đã quá ngày dự kiến hoặc trạng thái không cập nhật, hãy chọn **Cần nhân viên hỗ trợ**, '
                 'cung cấp mã đơn và thời điểm dự kiến nhận. Nhân viên sẽ kiểm tra nguyên nhân chậm và thông '
                 'báo hướng xử lý; Chatbot không tự cam kết ngày giao mới.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'chưa nhận được hàng',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Rất tiếc vì bạn vẫn chưa nhận được kiện hàng.\n'
                 '\n'
                 '• Nếu đơn **đang giao**: kiểm tra số điện thoại nhận hàng và lần cập nhật vận chuyển.\n'
                 '• Nếu hệ thống báo **đã giao** nhưng bạn chưa nhận: hỏi người nhận hộ/bộ phận lễ tân (nếu '
                 'có), ghi lại thời gian trạng thái chuyển sang đã giao.\n'
                 '\n'
                 'Sau đó chọn **Cần nhân viên hỗ trợ**, cung cấp mã đơn và tình trạng thực tế. Nhân viên sẽ '
                 'đối chiếu thông tin bàn giao, tránh kết luận thất lạc khi chưa xác minh.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'giao không thành công',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Trạng thái **giao không thành công** có thể do không liên lạc được người nhận, sai thông '
                 'tin hoặc phát sinh trong quá trình vận chuyển; cần kiểm tra lý do cụ thể theo vận đơn.\n'
                 '\n'
                 'Bạn hãy xác nhận lại số điện thoại, địa chỉ và thời điểm có thể nhận. Tiếp theo chọn **Cần '
                 'nhân viên hỗ trợ**, gửi mã đơn và thông tin cần điều chỉnh để nhân viên kiểm tra khả năng '
                 'giao lại hoặc hướng xử lý khác. **Không tự mặc định đơn sẽ được giao lại.**',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'giao sai địa chỉ',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Nếu thấy đơn đang được giao đến địa chỉ không chính xác, bạn nên báo ngay để hạn chế giao '
                 'nhầm.\n'
                 '\n'
                 'Hãy chuẩn bị **mã đơn, địa chỉ đúng (đủ số nhà/đường/phường), số điện thoại nhận hàng** và '
                 'chọn **Cần nhân viên hỗ trợ**. Nhân viên sẽ kiểm tra xem đơn còn có thể điều chỉnh hay '
                 'không và hướng dẫn bước tiếp theo. Nếu đã phát sinh giao nhầm, hãy nêu rõ trạng thái hiển '
                 'thị và thời điểm phát hiện.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'phí vận chuyển',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Phí vận chuyển có thể khác nhau theo địa chỉ nhận, khối lượng/kích thước kiện và cách giao '
                 'hàng. Vì vậy mình không muốn báo một mức phí cố định khi chưa có thông tin đơn.\n'
                 '\n'
                 'Bạn hãy xem khoản phí vận chuyển trong phần tổng tiền của đơn. Nếu phí hiển thị khác lúc '
                 'đặt hàng hoặc bị thu thêm khi nhận, lưu ảnh chụp số tiền và chọn **Cần nhân viên hỗ trợ**, '
                 'cung cấp mã đơn để nhân viên đối chiếu.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Giao hàng',
  'tu_khoa': 'mã vận đơn',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': '**Mã đơn hàng** dùng để quản lý đơn tại HULO, còn **mã vận đơn** dùng để theo dõi kiện '
                 'hàng trong quá trình giao nhận. Hai mã có thể khác nhau.\n'
                 '\n'
                 'Bạn hãy mở chi tiết đơn và xem phần vận chuyển. Nếu chưa có mã vận đơn, có thể đơn chưa '
                 'được cập nhật thông tin giao; hãy chọn **Cần nhân viên hỗ trợ** và gửi mã đơn để nhân viên '
                 'xác minh thay vì dự đoán.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'đổi hàng',
  'thu_tu_uu_tien': 55,
  'cau_tra_loi': 'Mình sẽ hướng dẫn bạn yêu cầu đổi hàng theo đúng quy trình nhé.\n'
                 '\n'
                 '**Bước 1:** Giữ sản phẩm, phụ kiện và bao bì nếu còn; chưa tự gửi trả hàng.\n'
                 '**Bước 2:** Chuẩn bị mã đơn, tên sản phẩm, lý do đổi và ảnh thể hiện tình trạng thực tế.\n'
                 '**Bước 3:** Chọn **Cần nhân viên hỗ trợ** để gửi yêu cầu.\n'
                 '\n'
                 'Nhân viên sẽ kiểm tra điều kiện áp dụng, xác minh thông tin và thông báo phương án đổi phù '
                 'hợp. Việc được đổi hay không phụ thuộc kết quả kiểm tra và chính sách của đơn.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'trả hàng',
  'thu_tu_uu_tien': 55,
  'cau_tra_loi': 'Nếu bạn muốn trả sản phẩm, trước tiên hãy giữ nguyên tình trạng hàng và các phụ kiện liên '
                 'quan nếu có.\n'
                 '\n'
                 'Chuẩn bị **mã đơn, sản phẩm muốn trả, lý do trả, thời điểm nhận hàng**, kèm ảnh lỗi/sai '
                 'khác (nếu có). Chọn **Cần nhân viên hỗ trợ** để nhân viên đánh giá điều kiện và hướng dẫn '
                 'quy trình nhận lại hàng. Bạn không nên tự gửi kiện về khi chưa có hướng dẫn tiếp nhận.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'hoàn tiền',
  'thu_tu_uu_tien': 60,
  'cau_tra_loi': 'Mình hiểu bạn muốn làm rõ quyền lợi hoàn tiền. Để tránh nhầm lẫn, **gửi yêu cầu hoàn tiền '
                 'không đồng nghĩa khoản tiền đã được phê duyệt hoặc chuyển trả**.\n'
                 '\n'
                 'Bạn hãy cung cấp mã đơn, sản phẩm/khoản thanh toán liên quan, lý do hoàn và minh chứng nếu '
                 'có qua **Cần nhân viên hỗ trợ**. Nhân viên sẽ xác minh, đề xuất hướng giải quyết và chuyển '
                 'phê duyệt theo quy trình nếu cần. Kết quả và thời gian hoàn chỉ được thông báo sau khi '
                 'kiểm tra trường hợp cụ thể.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'đổi sản phẩm',
  'thu_tu_uu_tien': 60,
  'cau_tra_loi': 'Nếu sản phẩm không phù hợp hoặc có vấn đề, mình có thể giúp bạn chuẩn bị yêu cầu đổi rõ '
                 'ràng để được xử lý nhanh hơn.\n'
                 '\n'
                 'Vui lòng ghi **mã đơn, tên sản phẩm, nguyên nhân muốn đổi** (lỗi kỹ thuật, giao sai, không '
                 'đúng mô tả...) và đính kèm ảnh tình trạng hàng nếu có. Sau đó chọn **Cần nhân viên hỗ '
                 'trợ**; nhân viên sẽ kiểm tra điều kiện đổi và phản hồi phương án phù hợp, chưa thể xác '
                 'nhận đổi ngay trên Chatbot.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'đổi nhầm hàng',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Rất tiếc vì bạn nhận sản phẩm không đúng. Để bộ phận hỗ trợ đối chiếu chính xác:\n'
                 '\n'
                 '1. Giữ lại sản phẩm nhận được, hộp và tem vận chuyển.\n'
                 '2. Chụp ảnh sản phẩm thực nhận và ảnh thông tin đơn đặt.\n'
                 '3. Chọn **Cần nhân viên hỗ trợ**, gửi mã đơn, sản phẩm đã đặt và sản phẩm thực nhận.\n'
                 '\n'
                 'Nhân viên sẽ kiểm tra sai lệch trước khi hướng dẫn đổi/thu hồi. Bạn chưa nên tự gửi trả '
                 'khi chưa nhận hướng dẫn.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'đổi hàng bị lỗi',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Rất tiếc vì sản phẩm của bạn gặp lỗi. Bạn có thể đề nghị kiểm tra để đổi hàng hoặc áp dụng '
                 'hướng xử lý khác phù hợp.\n'
                 '\n'
                 '**Chuẩn bị:** mã đơn, tên sản phẩm, mô tả lỗi cụ thể, thời điểm phát hiện và ảnh/video '
                 'minh họa. Nếu sản phẩm có nguy cơ mất an toàn, hãy ngừng sử dụng.\n'
                 '\n'
                 'Chọn **Cần nhân viên hỗ trợ** để tạo yêu cầu; nhân viên sẽ xác minh lỗi và điều kiện '
                 'đổi/bảo hành trước khi thông báo kết quả.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Đổi hàng / Đổi trả',
  'tu_khoa': 'quy trình đổi trả',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Quy trình yêu cầu đổi/trả tại HULO được tiếp nhận qua bộ phận hỗ trợ:\n'
                 '\n'
                 '**1. Gửi yêu cầu:** cung cấp mã đơn, sản phẩm, lý do, ảnh minh chứng nếu có.\n'
                 '**2. Kiểm tra:** nhân viên đối chiếu đơn và điều kiện theo chính sách áp dụng.\n'
                 '**3. Thông báo phương án:** nếu đủ điều kiện, nhân viên hướng dẫn cách bàn giao/nhận lại '
                 'hàng và bước tiếp theo.\n'
                 '**4. Theo dõi kết quả:** lưu mã Ticket để nhận cập nhật.\n'
                 '\n'
                 'Bạn hãy chọn **Cần nhân viên hỗ trợ** để bắt đầu; không tự gửi hàng khi chưa được hướng '
                 'dẫn.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'thanh toán đơn hàng',
  'thu_tu_uu_tien': 55,
  'cau_tra_loi': 'Bạn cần kiểm tra việc thanh toán đơn? Hãy mở đơn để xem **số tiền, phương thức thanh toán '
                 'và trạng thái được ghi nhận**.\n'
                 '\n'
                 'Nếu đã thanh toán nhưng đơn chưa cập nhật, hãy đối chiếu ứng dụng ngân hàng/ví và tránh '
                 'thanh toán lại ngay. Chọn **Cần nhân viên hỗ trợ**, gửi mã đơn, thời điểm và mã tham chiếu '
                 'giao dịch (nếu có). **Không gửi OTP, mật khẩu hay toàn bộ thông tin thẻ.**',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'thanh toán thất bại',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Mình hiểu việc thanh toán báo lỗi khiến bạn lo đơn chưa được ghi nhận. Trước khi thử lại, '
                 'bạn hãy:\n'
                 '\n'
                 '1. Kiểm tra thông báo lỗi và trạng thái giao dịch trong ứng dụng thanh toán.\n'
                 '2. Xem số dư có bị trừ hay giao dịch đang chờ xử lý không.\n'
                 '3. Nếu đã trừ tiền hoặc chưa rõ kết quả, **đừng thanh toán lặp lại ngay**.\n'
                 '\n'
                 'Chọn **Cần nhân viên hỗ trợ**, cung cấp mã đơn, thời điểm và mã giao dịch để đối chiếu an '
                 'toàn. Không chia sẻ OTP hoặc mật khẩu.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'bị trừ tiền',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Mình hiểu việc tài khoản đã trừ tiền nhưng đơn chưa xác nhận thanh toán rất đáng lo. Bạn '
                 '**không nên trả tiền lần nữa** cho đến khi xác minh giao dịch đầu tiên.\n'
                 '\n'
                 '**Hãy thực hiện:** (1) kiểm tra trạng thái giao dịch trong ngân hàng/ví; (2) giữ mã đơn, '
                 'số tiền, thời điểm và mã tham chiếu giao dịch; (3) chọn **Cần nhân viên hỗ trợ** để nhân '
                 'viên đối chiếu thanh toán với đơn.\n'
                 '\n'
                 'Bạn có thể che thông tin nhạy cảm trên ảnh minh chứng. **Không cung cấp OTP, mật khẩu hoặc '
                 'toàn bộ số thẻ.**',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'thanh toán hai lần',
  'thu_tu_uu_tien': 70,
  'cau_tra_loi': 'Nếu nghi ngờ bị thanh toán hai lần, trước tiên hãy kiểm tra xem cả hai giao dịch đã hoàn '
                 'tất hay một giao dịch vẫn ở trạng thái chờ.\n'
                 '\n'
                 'Bạn hãy ghi lại **mã đơn, số tiền, thời gian và mã tham chiếu của từng giao dịch**, tránh '
                 'gửi thông tin bảo mật. Sau đó chọn **Cần nhân viên hỗ trợ** để nhân viên kiểm tra khoản '
                 'thu trùng và hướng dẫn phương án xử lý nếu xác nhận có trùng. Chatbot không tự hoàn tiền.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'chuyển khoản',
  'thu_tu_uu_tien': 60,
  'cau_tra_loi': 'Khi thanh toán chuyển khoản, hãy chỉ sử dụng **thông tin người nhận và nội dung chuyển '
                 'khoản được xác nhận qua kênh chính thức**; không chuyển theo thông tin lạ gửi qua tin '
                 'nhắn.\n'
                 '\n'
                 'Nếu đã chuyển nhưng đơn chưa cập nhật, giữ lại mã đơn, số tiền, thời điểm và mã tham chiếu '
                 'giao dịch. Chọn **Cần nhân viên hỗ trợ** để đối chiếu trước khi chuyển lại. Tuyệt đối '
                 'không cung cấp OTP hoặc mật khẩu ngân hàng.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'cod',
  'thu_tu_uu_tien': 60,
  'cau_tra_loi': 'COD là hình thức thanh toán khi nhận hàng. **COD có áp dụng cho đơn của bạn hay không** '
                 'cần kiểm tra ở bước đặt hàng hoặc thông tin đơn đã tạo.\n'
                 '\n'
                 'Bạn hãy mở đơn để xác nhận phương thức thanh toán và tổng tiền dự kiến phải trả. Nếu người '
                 'giao yêu cầu thu khoản khác với thông tin đơn, hãy kiểm tra lại trước khi thanh toán và '
                 'chọn **Cần nhân viên hỗ trợ** để đối chiếu.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'hóa đơn',
  'thu_tu_uu_tien': 60,
  'cau_tra_loi': 'Bạn muốn xem hoặc yêu cầu hóa đơn cho đơn hàng? Hãy chuẩn bị **mã đơn, ngày mua và thông '
                 'tin cần thể hiện trên hóa đơn**.\n'
                 '\n'
                 'Chọn **Cần nhân viên hỗ trợ** để nhân viên kiểm tra chứng từ, điều kiện và cách cung cấp '
                 'hóa đơn theo quy trình hiện hành. Nếu cần điều chỉnh thông tin hóa đơn, bạn nên thông báo '
                 'sớm và nêu rõ phần cần sửa.',
  'dang_hoat_dong': True},
 {'ten_chu_de': 'Thanh toán',
  'tu_khoa': 'phương thức thanh toán',
  'thu_tu_uu_tien': 60,
  'cau_tra_loi': 'Phương thức thanh toán khả dụng phụ thuộc lựa chọn được cấu hình tại thời điểm đặt hàng; '
                 'mình không muốn khẳng định một hình thức được hỗ trợ khi chưa kiểm tra đơn.\n'
                 '\n'
                 'Bạn hãy xem các lựa chọn hiện trên trang đặt hàng hoặc phần thanh toán của đơn. Nếu muốn '
                 'đổi phương thức, bị báo lỗi hay có khoản thu chưa rõ, chọn **Cần nhân viên hỗ trợ** và '
                 'cung cấp mã đơn để được kiểm tra.',
  'dang_hoat_dong': True}]

EXISTING_RESPONSES = {
    "thanh toán": ("Bạn đang cần hỗ trợ về **thanh toán đơn hàng, chuyển khoản, COD hay một giao dịch bị lỗi**?\n\n• Nếu chưa biết đã thanh toán thành công: xem trạng thái giao dịch trong ngân hàng/ví và trạng thái đơn; **không thanh toán lại vội**.\n• Nếu đã trừ tiền nhưng đơn chưa ghi nhận: lưu mã đơn, số tiền, thời điểm và mã tham chiếu giao dịch.\n• Nếu muốn đổi cách thanh toán: kiểm tra phương thức hiện có trong đơn trước khi gửi yêu cầu.\n\nBạn có thể nói rõ trường hợp, ví dụ **'bị trừ tiền'** hoặc **'thanh toán thất bại'**. Khi cần xác minh, chọn **Cần nhân viên hỗ trợ**. Không cung cấp OTP, mật khẩu hay số thẻ đầy đủ.", 15),
    "đổi": ("Bạn muốn **đổi sản phẩm lỗi, đổi vì nhận sai hàng hay hỏi điều kiện đổi trả**?\n\nHãy giữ lại sản phẩm và phụ kiện, chuẩn bị mã đơn, lý do đổi cùng ảnh minh chứng. Chọn **Cần nhân viên hỗ trợ** để nhân viên kiểm tra điều kiện và hướng dẫn; **chưa nên tự gửi hàng trả**. Nếu cho biết cụ thể tình huống, mình có thể hướng dẫn những thông tin cần chuẩn bị.", 15),
    "đổi trả": ("Nếu bạn cần **đổi hoặc trả sản phẩm**, quy trình bắt đầu bằng việc gửi mã đơn, lý do yêu cầu và ảnh sản phẩm nếu có. Nhân viên sẽ kiểm tra điều kiện áp dụng, sau đó hướng dẫn cách bàn giao/nhận lại hàng và cập nhật kết quả qua Ticket.\n\nBạn đang muốn đổi do lỗi, nhận sai sản phẩm hay trả vì lý do khác? Hãy chọn **Cần nhân viên hỗ trợ** để tạo yêu cầu chính thức, không tự gửi trả khi chưa có hướng dẫn.", 15),
}

def main():
    missing = [r["tu_khoa"] for r in RULES if not ChatRule.objects.filter(tu_khoa=r["tu_khoa"]).exists()]
    missing += [k for k in EXISTING_RESPONSES if not ChatRule.objects.filter(tu_khoa=k).exists()]
    if missing:
        print("Thiếu từ khóa; chưa thay đổi dữ liệu:", ", ".join(missing))
        return
    with transaction.atomic():
        for rule in RULES:
            ChatRule.objects.filter(tu_khoa=rule["tu_khoa"]).update(
                cau_tra_loi=rule["cau_tra_loi"],
                ten_chu_de=rule["ten_chu_de"],
                thu_tu_uu_tien=rule["thu_tu_uu_tien"],
                dang_hoat_dong=True,
            )
        for keyword, (answer, priority) in EXISTING_RESPONSES.items():
            ChatRule.objects.filter(tu_khoa=keyword).update(
                cau_tra_loi=answer, thu_tu_uu_tien=priority, dang_hoat_dong=True,
            )
    print(f"Da nang cap noi dung {len(RULES) + len(EXISTING_RESPONSES)} quy tac. Tong ChatRule: {ChatRule.objects.count()}")

if __name__ == "__main__":
    main()
