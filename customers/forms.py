from uuid import uuid4
from django import forms

from .models import CareRecord
from .models import CSAT
from .models import LoyaltyReward


class CareInteractionForm(forms.ModelForm):

    class Meta:
        model = CareRecord

        fields = [
            'care_type',
            'content'
        ]

        widgets = {
            'content': forms.Textarea(
                attrs={
                    'class': 'm5-care-textarea',
                    'placeholder': (
                        'Nhập nội dung trao đổi, '
                        'kết quả chăm sóc khách hàng...'
                    ),
                    'rows': 5,
                    'maxlength': 500,
                }
            ),
        }

        labels = {
            'care_type': 'Hình thức chăm sóc',
            'content': 'Nội dung chăm sóc',
        }

    def clean_care_type(self):
        care_type = self.cleaned_data['care_type']

        allowed_types = [
            CareRecord.CareType.CALL,
            CareRecord.CareType.MESSAGE,
            CareRecord.CareType.OTHER,
        ]

        if care_type not in allowed_types:
            raise forms.ValidationError(
                'Hình thức chăm sóc không hợp lệ.'
            )

        return care_type

    def clean_content(self):
        content = self.cleaned_data['content'].strip()

        if not content:
            raise forms.ValidationError(
                'Vui lòng nhập nội dung chăm sóc.'
            )

        return content
class CSATForm(forms.ModelForm):
    class Meta:
        model = CSAT
        fields = ["score", "comment"]
        widgets = {
            "comment": forms.Textarea(
                attrs={
                    "placeholder": "Đánh giá của bạn sẽ giúp HULO cải thiện dịch vụ tốt hơn...",
                    "rows": 4,
                }
            )
        }


from django import forms
from .models import LoyaltyTransaction



class LoyaltyPointForm(forms.Form):

    # Mã duy nhất cho mỗi lần mở biểu mẫu
    idempotency_key = forms.UUIDField(
        widget=forms.HiddenInput(),
        required=True
    )

    transaction_type = forms.ChoiceField(
        label="Loại giao dịch",
        choices=LoyaltyTransaction.TransactionType.choices
    )

    points = forms.IntegerField(
        label="Số điểm",
        min_value=1,
        max_value=10000,
        widget=forms.NumberInput(
            attrs={
                "min": 1,
                "max": 10000,
                "placeholder": "Nhập số điểm"
            }
        )
    )

    description = forms.CharField(
        label="Lý do giao dịch",
        min_length=5,
        max_length=240,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Nhập lý do cộng hoặc đổi điểm"
            }
        )
    )
class LoyaltyVoucherTransactionForm(forms.Form):
    idempotency_key = forms.UUIDField(
        widget=forms.HiddenInput(),
    )

    transaction_type = forms.ChoiceField(
        label='Loại giao dịch',
        choices=[
            ('EARN', 'Cộng điểm'),
            ('REDEEM', 'Đổi điểm lấy Voucher'),
        ],
    )

    points = forms.IntegerField(
        label='Số điểm cộng',
        min_value=1,
        max_value=10000,
        required=False,
        widget=forms.NumberInput(attrs={
            'min': 1,
            'max': 10000,
            'placeholder': 'Nhập số điểm cần cộng',
        }),
    )

    reward = forms.ModelChoiceField(
        label='Voucher muốn đổi',
        queryset=LoyaltyReward.objects.none(),
        required=False,
        empty_label='Chọn Voucher',
    )

    description = forms.CharField(
        label='Lý do giao dịch',
        min_length=5,
        max_length=240,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Nhập lý do cộng điểm hoặc đổi Voucher',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['reward'].queryset = (
            LoyaltyReward.objects
            .filter(is_enabled=True)
            .order_by('points_cost', 'pk')
        )

    def clean(self):
        cleaned = super().clean()
        transaction_type = cleaned.get('transaction_type')

        if transaction_type == 'EARN':
            if cleaned.get('points') is None:
                self.add_error('points', 'Vui lòng nhập số điểm cộng.')

        elif transaction_type == 'REDEEM':
            if cleaned.get('reward') is None:
                self.add_error('reward', 'Vui lòng chọn Voucher.')

        return cleaned