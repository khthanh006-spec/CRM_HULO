
from django import forms
from django.contrib.auth import get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from customers.models import Customer


class CustomerRegisterForm(forms.Form):
    ho_ten = forms.CharField(
        label="Họ và tên",
        max_length=150,
    )

    username = forms.CharField(
        label="Tên đăng nhập",
        max_length=150,
    )

    email = forms.EmailField(
        label="Email",
    )

    so_dien_thoai = forms.CharField(
        label="Số điện thoại",
        max_length=20,
        required=False,
    )

    password1 = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput,
    )

    password2 = forms.CharField(
        label="Xác nhận mật khẩu",
        widget=forms.PasswordInput,
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        User = get_user_model()

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(
                "Tên đăng nhập đã tồn tại."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        User = get_user_model()

        if (
            User.objects.filter(email__iexact=email).exists()
            or Customer.objects.filter(email__iexact=email).exists()
        ):
            raise forms.ValidationError(
                "Email đã được sử dụng."
            )

        return email

    def clean(self):
        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2:
            if password1 != password2:
                self.add_error(
                    "password2",
                    "Mật khẩu xác nhận không khớp."
                )

            else:
                try:
                    validate_password(password1)
                except ValidationError as error:
                    self.add_error("password1", error)

        return cleaned_data


@require_http_methods(["GET", "POST"])
def register_view(request):

    # Chỉ cho phép chuyển tiếp đến chức năng
    # yêu cầu nhân viên hỗ trợ của CRM HULO.
    support_url = reverse("chatbot:chuyen_ho_tro")

    # Nhận địa chỉ chuyển tiếp từ URL hoặc biểu mẫu.
    next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or ""
    )

    # Không cho phép chuyển hướng đến địa chỉ tùy ý.
    if next_url != support_url:
        next_url = ""

    # Tài khoản đã đăng nhập không cần đăng ký lại.
    if request.user.is_authenticated:
        if next_url:
            return redirect(next_url)

        return redirect("home")

    form = CustomerRegisterForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        User = get_user_model()

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data["username"],
                    email=data["email"],
                    password=data["password1"],
                )

                Customer.objects.create(
                    ma_tai_khoan=user,
                    ho_ten=data["ho_ten"].strip(),
                    email=data["email"],
                    so_dien_thoai=(
                        data["so_dien_thoai"].strip()
                        or None
                    ),
                )

        except IntegrityError:
            form.add_error(
                None,
                "Thông tin đăng ký đã tồn tại. Vui lòng kiểm tra lại."
            )

        else:
            login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend",
            )

            # Đăng ký từ nút Cần nhân viên hỗ trợ:
            # quay lại đúng chức năng hỗ trợ.
            if next_url:
                return redirect(next_url)

            # Đăng ký thông thường:
            # trở về Trung tâm trợ giúp.
            return redirect("support:home")

    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
            "next_url": next_url,
        },
    )
