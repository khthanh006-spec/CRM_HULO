
import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .services import tra_loi_chatbot
from .views import chatbot_send_message


@require_POST
def guest_or_customer_send_message(request):
    """
    Khách vãng lai:
        Hỏi Chatbot tự động, không lưu lịch sử.

    Khách đã đăng nhập:
        Sử dụng chức năng Chatbot M2 hiện tại.
    """

    # Giữ nguyên quy trình của khách đã đăng nhập.
    if request.user.is_authenticated:
        return chatbot_send_message(request)

    # Đọc nội dung câu hỏi từ JSON.
    try:
        du_lieu = json.loads(request.body)

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {
                "error": "Dữ liệu gửi lên không hợp lệ."
            },
            status=400,
        )

    if not isinstance(du_lieu, dict):
        return JsonResponse(
            {
                "error": "Định dạng dữ liệu không hợp lệ."
            },
            status=400,
        )

    cau_hoi = du_lieu.get("cau_hoi", "")

    if not isinstance(cau_hoi, str):
        return JsonResponse(
            {
                "error": "Nội dung câu hỏi không hợp lệ."
            },
            status=400,
        )

    cau_hoi = cau_hoi.strip()

    if not cau_hoi:
        return JsonResponse(
            {
                "error": "Vui lòng nhập câu hỏi."
            },
            status=400,
        )

    if len(cau_hoi) > 1000:
        return JsonResponse(
            {
                "error": "Câu hỏi không được vượt quá 1000 ký tự."
            },
            status=400,
        )

    # Chỉ sử dụng bộ quy tắc Chatbot công khai.
    # Không truy vấn thông tin đơn hàng hay Ticket cá nhân.
    ket_qua = tra_loi_chatbot(cau_hoi)

    # Không tạo ChatSession hoặc ChatMessage.
    # Giữ định dạng phản hồi cho JavaScript hiện tại.
    return JsonResponse(
        {
            "cau_tra_loi": ket_qua["cau_tra_loi"],
            "ma_phien": None,
            "ma_tin_nhan": None,
        }
    )
