
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from PIL import Image, UnidentifiedImageError


class CustomerTicketSupplementForm(forms.Form):
    """
    Form khách hàng bổ sung thông tin và minh chứng.

    Chỉ xử lý việc kiểm tra dữ liệu đầu vào.
    Quyền sở hữu Ticket và trạng thái Ticket
    sẽ được kiểm tra trong View.

    Mỗi lần gửi hỗ trợ tối đa một tệp.
    """

    MAX_FILE_SIZE = 5 * 1024 * 1024

    noi_dung = forms.CharField(
        label="Nội dung bổ sung",
        required=True,
        min_length=10,
        max_length=5000,
        widget=forms.Textarea(
            attrs={
                "class": "ticket-message-textarea",
                "rows": 5,
                "placeholder": (
                    "Mô tả thông tin bổ sung, "
                    "sản phẩm thực tế đã nhận hoặc "
                    "nội dung cần HULOECOM kiểm tra..."
                ),
            }
        ),
        error_messages={
            "required": (
                "Vui lòng nhập nội dung bổ sung."
            ),
            "min_length": (
                "Nội dung phải có ít nhất 10 ký tự."
            ),
            "max_length": (
                "Nội dung không được vượt quá "
                "5000 ký tự."
            ),
        },
    )

    tep_minh_chung = forms.FileField(
        label="Ảnh hoặc tài liệu minh chứng",
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "jpg",
                    "jpeg",
                    "png",
                    "pdf",
                ]
            )
        ],
        widget=forms.ClearableFileInput(
            attrs={
                "class": "customer-ticket-file-input",
                "accept": (
                    ".jpg,.jpeg,.png,.pdf"
                ),
            }
        ),
        help_text=(
            "Hỗ trợ JPG, JPEG, PNG, PDF. "
            "Dung lượng tối đa 5 MB."
        ),
    )

    def clean_noi_dung(self):
        noi_dung = (
            self.cleaned_data.get("noi_dung") or ""
        ).strip()

        if len(noi_dung) < 10:
            raise ValidationError(
                "Nội dung phải có ít nhất 10 ký tự."
            )

        return noi_dung

    def clean_tep_minh_chung(self):
        uploaded_file = self.cleaned_data.get(
            "tep_minh_chung"
        )

        if uploaded_file is None:
            return None

        if uploaded_file.size <= 0:
            raise ValidationError(
                "Tệp minh chứng không được để trống."
            )

        if uploaded_file.size > self.MAX_FILE_SIZE:
            raise ValidationError(
                "Tệp minh chứng không được vượt quá 5 MB."
            )

        extension = (
            uploaded_file.name.rsplit(".", 1)[-1]
            .lower()
        )

        if extension in ("jpg", "jpeg", "png"):
            try:
                uploaded_file.seek(0)

                with Image.open(uploaded_file) as image:
                    detected_format = image.format
                    image.verify()

                expected_formats = {
                    "jpg": "JPEG",
                    "jpeg": "JPEG",
                    "png": "PNG",
                }

                if detected_format != expected_formats[extension]:
                    raise ValidationError(
                        "Định dạng ảnh không khớp "
                        "với phần mở rộng của tệp."
                    )

            except (
                UnidentifiedImageError,
                OSError,
                ValueError,
                SyntaxError,
            ):
                raise ValidationError(
                    "Tệp ảnh không hợp lệ hoặc bị hỏng."
                )
            finally:
                uploaded_file.seek(0)

        elif extension == "pdf":
            uploaded_file.seek(0)
            signature = uploaded_file.read(5)
            uploaded_file.seek(0)

            if signature != b"%PDF-":
                raise ValidationError(
                    "Tệp PDF không hợp lệ."
                )

        return uploaded_file
