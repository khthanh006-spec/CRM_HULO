
from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [

    # UC-2.1: Trang Chatbot
    path(
        '',
        views.chatbot_home,
        name='home'
    ),

    # UC-2.1 + UC-2.2: Gửi tin nhắn
    path(
        'gui-tin-nhan/',
        views.chatbot_send_message,
        name='send_message'
    ),

    # UC-2.3: Chuyển sang nhân viên hỗ trợ
    path(
        'chuyen-ho-tro/',
        views.chuyen_ho_tro,
        name='chuyen_ho_tro'
    ),

    # UC-2.4: Khai báo thông tin yêu cầu
    path(
        'khai-bao-yeu-cau/',
        views.khai_bao_yeu_cau,
        name='khai_bao_yeu_cau'
    ),

    # UC-2.5: Cung cấp bằng chứng
    path(
        'bang-chung/',
        views.tai_bang_chung,
        name='bang_chung'
    ),



    # UC-2.5: Xóa bằng chứng đã tải
    path(
        'xoa-bang-chung/',
        views.xoa_bang_chung,
        name='xoa_bang_chung'
    ),

    # UC-2.6: Kiểm tra và xác nhận yêu cầu
    path(
        'xac-nhan-yeu-cau/',
        views.xac_nhan_yeu_cau,
        name='xac_nhan_yeu_cau'
    ),

    # UC-2.7: Giao diện bổ sung thông tin yêu cầu
    path(
        'bo-sung-yeu-cau/',
        views.bo_sung_yeu_cau,
        name='bo_sung_yeu_cau'
    ),

]