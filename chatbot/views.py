
import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from customers.models import Customer

from .models import ChatSession, ChatMessage
from .services import tra_loi_chatbot, chuan_bi_yeu_cau_cho_m3
from .forms import YeuCauHoTroForm, BangChungForm, BoSungYeuCauForm

from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from PIL import Image, UnidentifiedImageError
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
# ==================================================
# UC-2.1: HIỂN THỊ GIAO DIỆN CHATBOT
# ==================================================

@login_required(login_url='login')
def chatbot_home(request):

    # Bước 1: Xác định khách hàng đang đăng nhập
    khach_hang = Customer.objects.filter(
        ma_tai_khoan=request.user
    ).first()

    # Nếu tài khoản chưa có hồ sơ khách hàng
    if khach_hang is None:
        return HttpResponseForbidden(
            "Tài khoản chưa có hồ sơ khách hàng."
        )

    # Bước 2: Tìm phiên trò chuyện đang hoạt động
    phien_chat = ChatSession.objects.filter(
        ma_khach_hang=khach_hang,
        trang_thai='DANG_CHAT'
    ).order_by(
        '-thoi_diem_bat_dau',
        '-ma_phien'
    ).first()

    # Bước 3: Nếu chưa có phiên thì tạo phiên mới
    if phien_chat is None:
        phien_chat = ChatSession.objects.create(
            ma_khach_hang=khach_hang,
            trang_thai='DANG_CHAT',
            ket_qua='CHUA_XAC_DINH'
        )

    # Bước 4: Lấy lịch sử tin nhắn của phiên
    tin_nhan = ChatMessage.objects.filter(
        ma_phien=phien_chat
    ).order_by(
        'thoi_diem_gui',
        'ma_tin_nhan'
    )

    # Bước 5: Hiển thị giao diện Chatbot
    return render(
        request,
        'chatbot/home.html',
        {
            'phien_chat': phien_chat,
            'tin_nhan': tin_nhan
        }
    )


# ==================================================
# UC-2.1 + UC-2.2: GỬI VÀ XỬ LÝ TIN NHẮN
# ==================================================

@login_required(login_url='login')
@require_POST
def chatbot_send_message(request):

    # Bước 1: Xác định khách hàng đang đăng nhập
    khach_hang = Customer.objects.filter(
        ma_tai_khoan=request.user
    ).first()

    if khach_hang is None:
        return JsonResponse(
            {
                'error': 'Không tìm thấy hồ sơ khách hàng.'
            },
            status=403
        )

    # Bước 2: Nhận câu hỏi từ giao diện website
    try:
        du_lieu = json.loads(request.body)

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {
                'error': 'Dữ liệu gửi lên không hợp lệ.'
            },
            status=400
        )

    # Kiểm tra dữ liệu JSON
    if not isinstance(du_lieu, dict):
        return JsonResponse(
            {
                'error': 'Định dạng dữ liệu không hợp lệ.'
            },
            status=400
        )

    cau_hoi = du_lieu.get('cau_hoi', '')

    # Kiểm tra câu hỏi
    if not isinstance(cau_hoi, str):
        return JsonResponse(
            {
                'error': 'Nội dung câu hỏi không hợp lệ.'
            },
            status=400
        )

    cau_hoi = cau_hoi.strip()

    if not cau_hoi:
        return JsonResponse(
            {
                'error': 'Vui lòng nhập câu hỏi.'
            },
            status=400
        )

    # Giới hạn độ dài câu hỏi
    if len(cau_hoi) > 1000:
        return JsonResponse(
            {
                'error': 'Câu hỏi không được vượt quá 1000 ký tự.'
            },
            status=400
        )

    # Bước 3: Tìm hoặc tạo phiên và lưu tin nhắn
    with transaction.atomic():

        # Tìm phiên trò chuyện đang hoạt động
        phien_chat = ChatSession.objects.filter(
            ma_khach_hang=khach_hang,
            trang_thai='DANG_CHAT'
        ).order_by(
            '-thoi_diem_bat_dau',
            '-ma_phien'
        ).first()

        # SỬA LỖI: Nếu chưa có phiên, tự động tạo mới
        if phien_chat is None:
            phien_chat = ChatSession.objects.create(
                ma_khach_hang=khach_hang,
                trang_thai='DANG_CHAT',
                ket_qua='CHUA_XAC_DINH'
            )

        # Bước 4: Gọi hàm xử lý câu hỏi
        ket_qua = tra_loi_chatbot(cau_hoi)

        # Bước 5: Lưu tin nhắn của khách hàng
        ChatMessage.objects.create(
            ma_phien=phien_chat,
            ben_gui='KHACH_HANG',
            noi_dung=cau_hoi
        )

        # Bước 6: Lưu câu trả lời của Chatbot
        tin_nhan_bot = ChatMessage.objects.create(
            ma_phien=phien_chat,
            ben_gui='CHATBOT',
            noi_dung=ket_qua['cau_tra_loi'],
            ma_quy_tac=ket_qua['quy_tac']
        )

    # Bước 7: Trả kết quả về giao diện
    return JsonResponse({
        'cau_tra_loi': ket_qua['cau_tra_loi'],
        'ma_phien': phien_chat.ma_phien,
        'ma_tin_nhan': tin_nhan_bot.ma_tin_nhan
    })
# UC-2.3: CHUYỂN SANG NHÂN VIÊN HỖ TRỢ


# ==================================================
# UC-2.3: CHUYỂN SANG NHÂN VIÊN HỖ TRỢ
# ==================================================

@login_required(login_url='login')
def chuyen_ho_tro(request):

    # Bước 1: Xác định khách hàng đăng nhập
    khach_hang = Customer.objects.filter(
        ma_tai_khoan=request.user
    ).first()

    if khach_hang is None:
        return HttpResponseForbidden(
            "Tài khoản chưa có hồ sơ khách hàng."
        )

    # Bước 2: Danh sách vấn đề cần hỗ trợ
    danh_sach_loai = [
        ('DON_HANG', 'Vấn đề đơn hàng'),
        ('GIAO_HANG', 'Vấn đề giao hàng'),
        ('DOI_TRA', 'Đổi trả / Hoàn tiền'),
        ('THANH_TOAN', 'Vấn đề thanh toán'),
        ('SAN_PHAM_LOI', 'Sản phẩm bị lỗi'),
        ('KHAC', 'Vấn đề khác'),
    ]

    loi = None
    da_xac_nhan = False
    loai_da_chon = ''

    # Bước 3: Xử lý khi khách gửi biểu mẫu
    if request.method == 'POST':

        loai_da_chon = request.POST.get(
            'loai_van_de', ''
        )

        xac_nhan = request.POST.get(
            'xac_nhan'
        ) == 'on'

        if loai_da_chon not in dict(danh_sach_loai):
            loi = "Vui lòng chọn loại vấn đề."

        elif not xac_nhan:
            loi = "Vui lòng xác nhận yêu cầu hỗ trợ."

        else:
            # Bước 4: Lấy phiên Chatbot hiện tại
            phien_chat = ChatSession.objects.filter(
                ma_khach_hang=khach_hang,
                trang_thai='DANG_CHAT'
            ).order_by('-ma_phien').first()

            # Bước 5: Lưu tạm dữ liệu cho UC-2.4
            request.session['m2_yeu_cau_ho_tro'] = {
                'ma_khach_hang': khach_hang.pk,
                'ma_phien': (
                    phien_chat.pk if phien_chat else None
                ),
                'loai_van_de': loai_da_chon
            }

            da_xac_nhan = True

    # Bước 6: Hiển thị giao diện
    return render(
        request,
        'chatbot/chuyen_ho_tro.html',
        {
            'danh_sach_loai': danh_sach_loai,
            'loi': loi,
            'da_xac_nhan': da_xac_nhan,
            'loai_da_chon': loai_da_chon,
        }
    )

# ==================================================
# UC-2.4: KHAI BÁO THÔNG TIN YÊU CẦU HỖ TRỢ
# ==================================================

@login_required(login_url='login')
def khai_bao_yeu_cau(request):

    # Bước 1: Xác định khách hàng đang đăng nhập
    khach_hang = Customer.objects.filter(
        ma_tai_khoan=request.user
    ).first()

    if khach_hang is None:
        return HttpResponseForbidden(
            "Tài khoản chưa có hồ sơ khách hàng."
        )

    # Bước 2: Lấy loại vấn đề đã chọn tại UC-2.3
    yeu_cau = request.session.get(
        'm2_yeu_cau_ho_tro'
    )

    # Không cho bỏ qua bước chọn loại vấn đề
    if not isinstance(yeu_cau, dict):
        return redirect('chatbot:chuyen_ho_tro')

    # Kiểm tra bản nháp thuộc khách hàng hiện tại
    if yeu_cau.get('ma_khach_hang') != khach_hang.pk:
        return redirect('chatbot:chuyen_ho_tro')
    # UC-2.6: Tạo mã yêu cầu nguồn cho M3
    # Chỉ tạo một lần cho mỗi bản nháp
    if not yeu_cau.get('source_request_id'):
        yeu_cau['source_request_id'] = (
            f"M2-{uuid4().hex}"
        )

        request.session[
            'm2_yeu_cau_ho_tro'
        ] = yeu_cau
    # Các loại vấn đề hợp lệ
    ten_cac_loai = {
        'DON_HANG': 'Vấn đề đơn hàng',
        'GIAO_HANG': 'Vấn đề giao hàng',
        'DOI_TRA': 'Đổi trả / Hoàn tiền',
        'THANH_TOAN': 'Vấn đề thanh toán',
        'SAN_PHAM_LOI': 'Sản phẩm bị lỗi',
        'KHAC': 'Vấn đề khác',
    }

    loai_van_de = yeu_cau.get('loai_van_de')

    if loai_van_de not in ten_cac_loai:
        return redirect('chatbot:chuyen_ho_tro')

    da_luu = False

    # Bước 3: Xử lý dữ liệu khách hàng gửi lên
    if request.method == 'POST':

        form = YeuCauHoTroForm(request.POST)

        # Kiểm tra dữ liệu hợp lệ
        if form.is_valid():

            # Lưu bản nháp vào Django session
            yeu_cau['thong_tin'] = {
                'tieu_de': form.cleaned_data['tieu_de'],
                'ma_don_hang': form.cleaned_data['ma_don_hang'],
                'mo_ta': form.cleaned_data['mo_ta'],
                'email_lien_he': form.cleaned_data['email_lien_he'],
                'so_dien_thoai': form.cleaned_data['so_dien_thoai'],
            }

            request.session['m2_yeu_cau_ho_tro'] = yeu_cau

            da_luu = True

    else:

        # Bước 4: Hiển thị Form
        # Tự điền thông tin liên hệ nếu có
        du_lieu_ban_dau = {
            'email_lien_he': khach_hang.email,
            'so_dien_thoai': khach_hang.so_dien_thoai or '',
        }

        # Khôi phục dữ liệu bản nháp đã nhập trước đó
        du_lieu_ban_dau.update(
            yeu_cau.get('thong_tin', {})
        )

        form = YeuCauHoTroForm(
            initial=du_lieu_ban_dau
        )


    # Bước 5: Lấy danh sách bằng chứng đã tải
    danh_sach_tep = yeu_cau.get('bang_chung', [])

    if not isinstance(danh_sach_tep, list):
        danh_sach_tep = []

    # Bước 6: Lấy thông báo sau khi tải tệp
    thong_bao_tep = request.session.pop(
        'm2_thong_bao_tep',
        None
    )

    # Bước 7: Hiển thị giao diện chung
    return render(
        request,
        'chatbot/khai_bao_yeu_cau.html',
        {
            'form': form,
            'loai_van_de': loai_van_de,
            'ten_loai_van_de': ten_cac_loai[loai_van_de],
            'da_luu': da_luu,
            'co_ban_nhap': isinstance(
                yeu_cau.get('thong_tin'), dict
            ),
            'danh_sach_tep': danh_sach_tep,
            'thong_bao_tep': thong_bao_tep,
        }
    )



# ==================================================
# UC-2.5: CUNG CẤP BẰNG CHỨNG CHO YÊU CẦU
# ==================================================

@login_required(login_url='login')
def tai_bang_chung(request):

    # Bước 1: Xác định khách hàng
    khach_hang = Customer.objects.filter(
        ma_tai_khoan=request.user
    ).first()

    if khach_hang is None:
        return HttpResponseForbidden(
            "Tài khoản chưa có hồ sơ khách hàng."
        )

    # Bước 2: Lấy bản nháp UC-2.4
    yeu_cau = request.session.get(
        'm2_yeu_cau_ho_tro'
    )

    if not isinstance(yeu_cau, dict):
        return redirect('chatbot:chuyen_ho_tro')

    if yeu_cau.get('ma_khach_hang') != khach_hang.pk:
        return HttpResponseForbidden(
            "Bạn không có quyền truy cập yêu cầu này."
        )

    # Khách phải hoàn thành khai báo thông tin
    if not isinstance(yeu_cau.get('thong_tin'), dict):
        return redirect('chatbot:khai_bao_yeu_cau')

    danh_sach_tep = yeu_cau.get('bang_chung', [])

    if not isinstance(danh_sach_tep, list):
        danh_sach_tep = []

    thong_bao = None

    # Bước 3: Xử lý khi khách tải tệp
    if request.method == 'POST':

        form = BangChungForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            tep = form.cleaned_data['tep_bang_chung']

            # Giới hạn 5 tệp cho bản thực hành
            if len(danh_sach_tep) >= 5:
                form.add_error(
                    'tep_bang_chung',
                    'Chỉ được tải tối đa 5 tệp.'
                )

            else:

                # UC-2.5: Chỉ chấp nhận ảnh JPEG thật
                duoi_tep = Path(tep.name).suffix.lower()
                hop_le = False

                if duoi_tep in ('.jpg', '.jpeg'):
                    try:
                        tep.seek(0)

                        with Image.open(tep) as anh:
                            if (
                                anh.format == 'JPEG'
                                and anh.width * anh.height <= 20_000_000
                            ):
                                # Đọc dữ liệu ảnh để kiểm tra
                                anh.load()
                                hop_le = True

                    except (
                        UnidentifiedImageError,
                        OSError,
                        ValueError,
                        Image.DecompressionBombError
                    ):
                        hop_le = False

                    finally:
                        tep.seek(0)

                if not hop_le:
                    form.add_error(
                        'tep_bang_chung',
                        'Chỉ chấp nhận ảnh JPEG (JPG/JPEG) hợp lệ.'
                    )


                else:
                    # Bước 4: Lưu tệp riêng ngoài GitHub
                    thu_muc_rieng = (
                        settings.BASE_DIR.parent
                        / 'CRM_HULO_m2_private'
                    )

                    kho_luu_tru = FileSystemStorage(
                        location=str(thu_muc_rieng)
                    )

                    # Tạo tên ngẫu nhiên, tránh trùng tệp
                    ten_luu = (
                        f'kh_{khach_hang.pk}/'
                        f'{uuid4().hex}{duoi_tep}'
                    )

                    duong_dan_luu = kho_luu_tru.save(
                        ten_luu,
                        tep
                    )

                    # Chỉ lưu thông tin tệp vào session
                    danh_sach_tep.append({
                        'ten_goc': tep.name,
                        'duong_dan_luu': duong_dan_luu,
                        'dung_luong': tep.size,
                    })

                    yeu_cau['bang_chung'] = danh_sach_tep

                    request.session[
                        'm2_yeu_cau_ho_tro'
                    ] = yeu_cau

                    thong_bao = (
                        'Tải bằng chứng thành công!'
                    )

                    form = BangChungForm()

    else:
        form = BangChungForm()


    # Bước 5: Quay về trang khai báo nếu truy cập trực tiếp
    if request.method != 'POST':
        return redirect('chatbot:khai_bao_yeu_cau')

    # Bước 6: Lưu thông báo tải tệp
    if thong_bao:
        request.session['m2_thong_bao_tep'] = {
            'thanh_cong': True,
            'noi_dung': thong_bao
        }

    else:
        # Lấy lỗi nếu tệp không hợp lệ
        loi_tep = form.errors.get('tep_bang_chung')

        request.session['m2_thong_bao_tep'] = {
            'thanh_cong': False,
            'noi_dung': (
                str(loi_tep[0])
                if loi_tep
                else 'Tệp không hợp lệ.'
            )
        }

    # Bước 7: Trở về giao diện chung UC-2.4 + UC-2.5
    return redirect('chatbot:khai_bao_yeu_cau')

# ==================================================
# UC-2.5: XÓA BẰNG CHỨNG ĐÃ TẢI
# ==================================================

@login_required(login_url='login')
@require_POST
def xoa_bang_chung(request):

    import re

    # Bước 1: Xác định khách hàng
    khach_hang = Customer.objects.filter(
        ma_tai_khoan=request.user
    ).first()

    if khach_hang is None:
        return HttpResponseForbidden(
            "Không tìm thấy hồ sơ khách hàng."
        )

    # Bước 2: Lấy bản nháp hiện tại
    yeu_cau = request.session.get(
        'm2_yeu_cau_ho_tro'
    )

    if not isinstance(yeu_cau, dict):
        return redirect('chatbot:chuyen_ho_tro')

    if yeu_cau.get('ma_khach_hang') != khach_hang.pk:
        return HttpResponseForbidden(
            "Bạn không có quyền xóa bằng chứng này."
        )

    danh_sach_tep = yeu_cau.get('bang_chung', [])

    if not isinstance(danh_sach_tep, list):
        return redirect('chatbot:khai_bao_yeu_cau')

    # Bước 3: Xác định tệp cần xóa
    try:
        vi_tri = int(request.POST.get('vi_tri', ''))
    except (ValueError, TypeError):
        return redirect('chatbot:khai_bao_yeu_cau')

    if vi_tri < 0 or vi_tri >= len(danh_sach_tep):
        return redirect('chatbot:khai_bao_yeu_cau')

    tep_can_xoa = danh_sach_tep[vi_tri]
    ten_luu = tep_can_xoa.get('duong_dan_luu', '')

    # Bước 4: Kiểm tra đường dẫn thuộc khách hàng
    mau_ten = (
        rf'kh_{khach_hang.pk}/'
        r'[0-9a-f]{32}\.(jpg|jpeg|png|pdf|mp4)'
    )

    if not isinstance(ten_luu, str) or not re.fullmatch(
        mau_ten, ten_luu
    ):
        return HttpResponseForbidden(
            "Đường dẫn bằng chứng không hợp lệ."
        )

    # Bước 5: Xóa tệp khỏi khu vực lưu riêng
    thu_muc_rieng = (
        Path(settings.BASE_DIR).parent
        / 'CRM_HULO_m2_private'
    )

    kho_luu_tru = FileSystemStorage(
        location=str(thu_muc_rieng)
    )

    kho_luu_tru.delete(ten_luu)

    # Bước 6: Xóa thông tin khỏi bản nháp
    danh_sach_tep.pop(vi_tri)

    yeu_cau['bang_chung'] = danh_sach_tep

    request.session['m2_yeu_cau_ho_tro'] = yeu_cau

    # Bước 7: Thông báo thành công
    request.session['m2_thong_bao_tep'] = {
        'thanh_cong': True,
        'noi_dung': 'Đã xóa bằng chứng thành công!'
    }

    return redirect('chatbot:khai_bao_yeu_cau')


# ==================================================
# UC-2.6: KIỂM TRA VÀ XÁC NHẬN YÊU CẦU HỖ TRỢ
# ==================================================

@login_required(login_url='login')
def xac_nhan_yeu_cau(request):

    # Bước 1: Chỉ hiển thị trang kiểm tra
    if request.method != 'GET':
        return redirect('chatbot:khai_bao_yeu_cau')

    # Bước 2: Xác định khách hàng đang đăng nhập
    khach_hang = Customer.objects.filter(
        ma_tai_khoan=request.user
    ).first()

    if khach_hang is None:
        return HttpResponseForbidden(
            "Tài khoản chưa có hồ sơ khách hàng."
        )

    # Bước 3: Lấy yêu cầu đã lưu tạm
    yeu_cau = request.session.get(
        'm2_yeu_cau_ho_tro'
    )

    if not isinstance(yeu_cau, dict):
        return redirect('chatbot:chuyen_ho_tro')

    # Kiểm tra bản nháp thuộc khách hàng hiện tại
    if yeu_cau.get('ma_khach_hang') != khach_hang.pk:
        return HttpResponseForbidden(
            "Bạn không có quyền xem yêu cầu này."
        )

    # Bước 4: Lấy thông tin yêu cầu
    thong_tin = yeu_cau.get('thong_tin')

    if not isinstance(thong_tin, dict):
        return redirect('chatbot:khai_bao_yeu_cau')

    # Kiểm tra lại các thông tin đã lưu
    form = YeuCauHoTroForm(thong_tin)

    if not form.is_valid():
        return redirect('chatbot:khai_bao_yeu_cau')

    # Bước 5: Xác định tên loại vấn đề
    ten_cac_loai = {
        'DON_HANG': 'Vấn đề đơn hàng',
        'GIAO_HANG': 'Vấn đề giao hàng',
        'DOI_TRA': 'Đổi trả / Hoàn tiền',
        'THANH_TOAN': 'Vấn đề thanh toán',
        'SAN_PHAM_LOI': 'Sản phẩm bị lỗi',
        'KHAC': 'Vấn đề khác',
    }

    loai_van_de = yeu_cau.get('loai_van_de')

    if loai_van_de not in ten_cac_loai:
        return redirect('chatbot:chuyen_ho_tro')

    # Bước 6: Lấy danh sách bằng chứng
    danh_sach_tep = yeu_cau.get(
        'bang_chung', []
    )

    if not isinstance(danh_sach_tep, list):
        danh_sach_tep = []


    # Bước 7: Chuẩn bị dữ liệu M2 cho M3
    # Chưa tạo Ticket chính thức
    try:
        du_lieu_m3 = chuan_bi_yeu_cau_cho_m3(
            yeu_cau
        )

    except ValueError:
        return redirect('chatbot:khai_bao_yeu_cau')

    # Bước 8: Hiển thị trang kiểm tra yêu cầu
    return render(
        request,
        'chatbot/xac_nhan_yeu_cau.html',
        {
            'ten_loai_van_de': ten_cac_loai[loai_van_de],
            'thong_tin': form.cleaned_data,
            'danh_sach_tep': danh_sach_tep,
            'du_lieu_m3': du_lieu_m3,
        }
    )



# ==============================================
# UC-2.7: KIỂM TRA NỘI DUNG BỔ SUNG
# ==============================================

@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def bo_sung_yeu_cau(request):

    noi_dung_xem_truoc = None

    # Bước 1: Nếu khách hàng gửi nội dung để kiểm tra
    if request.method == 'POST':

        form = BoSungYeuCauForm(request.POST)

        # Bước 2: Kiểm tra nội dung hợp lệ
        if form.is_valid():

            noi_dung_xem_truoc = form.cleaned_data[
                'noi_dung_bo_sung'
            ]

    else:
        # Nếu chỉ mở trang thì hiển thị form trống
        form = BoSungYeuCauForm()

    # Bước 3: Hiển thị form và nội dung xem trước
    return render(
        request,
        'chatbot/bo_sung_yeu_cau.html',
        {
            'form': form,
            'noi_dung_xem_truoc': noi_dung_xem_truoc,
        }
    )
