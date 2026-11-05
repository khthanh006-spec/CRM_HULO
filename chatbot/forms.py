
from django import forms


# ==========================================
# UC-2.4: KHAI BÁO THÔNG TIN YÊU CẦU HỖ TRỢ
# ==========================================

class YeuCauHoTroForm(forms.Form):

    tieu_de = forms.CharField(
        label="Tiêu đề yêu cầu",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'm2-input',
            'placeholder': 'Ví dụ: Áo thun bị lỗi in'
        })
    )

    ma_don_hang = forms.CharField(
        label="Mã đơn hàng (nếu có)",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'm2-input',
            'placeholder': 'Ví dụ: ORD001'
        })
    )

    mo_ta = forms.CharField(
        label="Mô tả chi tiết vấn đề",
        min_length=10,
        max_length=2000,
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'm2-textarea',
            'rows': 5,
            'placeholder': 'Mô tả vấn đề bạn gặp phải...'
        })
    )

    email_lien_he = forms.EmailField(
        label="Email liên hệ",
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'm2-input',
            'placeholder': 'Nhập email liên hệ'
        })
    )

    so_dien_thoai = forms.CharField(
        label="Số điện thoại",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'm2-input',
            'placeholder': 'Nhập số điện thoại'
        })
    )


# ==================================================
# UC-2.5: FORM CUNG CẤP BẰNG CHỨNG
# Chỉ chấp nhận ảnh JPG/JPEG
# ==================================================

class BangChungForm(forms.Form):

    tep_bang_chung = forms.FileField(
        label='Chọn ảnh bằng chứng',
        required=True,
        widget=forms.ClearableFileInput(
            attrs={
                'accept': '.jpg,.jpeg'
            }
        )
    )

    def clean_tep_bang_chung(self):

        tep = self.cleaned_data['tep_bang_chung']

        # Bước 1: Kiểm tra phần mở rộng
        ten_tep = tep.name.lower()

        if not ten_tep.endswith(('.jpg', '.jpeg')):
            raise forms.ValidationError(
                'Chỉ chấp nhận ảnh JPG hoặc JPEG.'
            )

        # Bước 2: Kiểm tra dung lượng
        gioi_han = 10 * 1024 * 1024

        if tep.size > gioi_han:
            raise forms.ValidationError(
                'Ảnh không được vượt quá 10 MB.'
            )

        # Bước 3: Trả tệp hợp lệ về View
        return tep

# ==========================================
# UC-2.7: FORM BỔ SUNG THÔNG TIN YÊU CẦU
# ==========================================

class BoSungYeuCauForm(forms.Form):

    noi_dung_bo_sung = forms.CharField(
        label="Nội dung bổ sung",
        min_length=10,
        max_length=2000,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Nhập thông tin cần bổ sung...'
            }
        )
    )
