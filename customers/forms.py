
from django import forms

from .models import CareRecord


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
