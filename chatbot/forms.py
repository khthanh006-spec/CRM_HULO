
from django import forms

from disputes.models import Order


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
            'placeholder': 'Ví dụ: Đơn hàng giao chậm'
        })
    )

    ma_don_hang = forms.ChoiceField(
        label="Đơn hàng liên quan (nếu có)",
        required=False,
        choices=[
            ('', 'Không liên quan đến đơn hàng'),
        ],
        widget=forms.Select(attrs={
            'class': 'm2-input',
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

    def __init__(self, *args, customer=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.customer = customer

        choices = [
            ('', 'Không liên quan đến đơn hàng'),
        ]

        if customer is not None:

            orders = (
                Order.objects
                .filter(ma_khach_hang=customer)
                .order_by(
                    '-thoi_diem_dat',
                    '-ma_don_hang',
                )
            )

            status_labels = dict(
                Order._meta.get_field(
                    'trang_thai'
                ).choices
            )

            for order in orders:

                status = status_labels.get(
                    order.trang_thai,
                    order.trang_thai,
                )

                label = (
                    f'{order.so_don_hang} — {status}'
                )

                choices.append(
                    (order.so_don_hang, label)
                )

        self.fields['ma_don_hang'].choices = choices

    def clean_ma_don_hang(self):
        ma_don_hang = (
            self.cleaned_data.get('ma_don_hang') or ''
        ).strip()

        if not ma_don_hang:
            return ''

        if self.customer is None:
            raise forms.ValidationError(
                'Không xác định được khách hàng.'
            )

        exists = Order.objects.filter(
            so_don_hang=ma_don_hang,
            ma_khach_hang=self.customer,
        ).exists()

        if not exists:
            raise forms.ValidationError(
                'Đơn hàng không tồn tại hoặc không thuộc '
                'tài khoản của bạn.'
            )

        return ma_don_hang


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

        ten_tep = tep.name.lower()

        if not ten_tep.endswith(('.jpg', '.jpeg')):
            raise forms.ValidationError(
                'Chỉ chấp nhận ảnh JPG hoặc JPEG.'
            )

        gioi_han = 10 * 1024 * 1024

        if tep.size > gioi_han:
            raise forms.ValidationError(
                'Ảnh không được vượt quá 10 MB.'
            )

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
