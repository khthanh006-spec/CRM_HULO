from uuid import uuid4
from django import forms

from .models import CareRecord
from .models import CSAT


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
