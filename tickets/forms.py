
from django import forms

from .models import TicketMessage


class TicketMessageForm(forms.ModelForm):

    class Meta:
        model = TicketMessage

        fields = [
            'loai_tin_nhan',
            'noi_dung',
        ]

        labels = {
            'loai_tin_nhan': 'Loại nội dung',
            'noi_dung': 'Nội dung phản hồi',
        }

        widgets = {
            'loai_tin_nhan': forms.Select(
                attrs={
                    'class': 'ticket-filter-select',
                }
            ),

            'noi_dung': forms.Textarea(
                attrs={
                    'class': 'ticket-message-textarea',
                    'rows': 5,
                    'placeholder': (
                        'Nhập nội dung phản hồi hoặc '
                        'ghi chú xử lý Ticket...'
                    ),
                }
            ),
        }

    def clean_noi_dung(self):
        noi_dung = self.cleaned_data['noi_dung'].strip()

        if not noi_dung:
            raise forms.ValidationError(
                'Vui lòng nhập nội dung phản hồi.'
            )

        return noi_dung


# ==================================================
# UC-3.5 - FORM HOÀN TẤT XỬ LÝ TICKET
# ==================================================

class TicketResolveForm(forms.Form):

    ket_qua_xu_ly = forms.CharField(
        label='Kết quả xử lý Ticket',
        required=True,
        min_length=10,
        widget=forms.Textarea(
            attrs={
                'class': 'ticket-message-textarea',
                'rows': 5,
                'placeholder': (
                    'Mô tả kết quả xác minh, phương án giải quyết '
                    'và hướng xử lý dành cho khách hàng...'
                ),
            }
        ),
        error_messages={
            'required': 'Vui lòng nhập kết quả xử lý.',
            'min_length': 'Kết quả xử lý phải có ít nhất 10 ký tự.',
        }
    )

    def clean_ket_qua_xu_ly(self):
        ket_qua = self.cleaned_data['ket_qua_xu_ly'].strip()

        if len(ket_qua) < 10:
            raise forms.ValidationError(
                'Kết quả xử lý phải có ít nhất 10 ký tự.'
            )

        return ket_qua


# ==================================================
# UC-3.5 - KHÁCH HÀNG XÁC NHẬN KẾT QUẢ TICKET
# ==================================================

class TicketConfirmationForm(forms.Form):

    CONFIRMATION_CHOICES = [
        ('AGREE', 'Đồng ý với kết quả xử lý'),
        ('DISAGREE', 'Không đồng ý, yêu cầu xử lý lại'),
    ]

    lua_chon = forms.ChoiceField(
        label='Xác nhận kết quả xử lý',
        choices=CONFIRMATION_CHOICES,
        widget=forms.RadioSelect,
        required=True,
        error_messages={
            'required': 'Vui lòng chọn một phương án.'
        }
    )

    ly_do = forms.CharField(
        label='Lý do / Phản hồi bổ sung',
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': 'ticket-message-textarea',
                'rows': 4,
                'placeholder': (
                    'Nếu không đồng ý, vui lòng mô tả '
                    'lý do cần xử lý lại...'
                ),
            }
        )
    )

    def clean(self):
        cleaned_data = super().clean()

        lua_chon = cleaned_data.get('lua_chon')
        ly_do = (cleaned_data.get('ly_do') or '').strip()

        if lua_chon == 'DISAGREE' and not ly_do:
            self.add_error(
                'ly_do',
                'Vui lòng nhập lý do không đồng ý.'
            )

        cleaned_data['ly_do'] = ly_do

        return cleaned_data
