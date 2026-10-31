
"""
Django settings for CRM HULO project.
Django version: 5.2.18
"""

import os
from pathlib import Path


# 1. ĐƯỜNG DẪN THƯ MỤC GỐC
BASE_DIR = Path(__file__).resolve().parent.parent


# 2. BẢO MẬT VÀ MÔI TRƯỜNG PHÁT TRIỂN

# Đọc SECRET_KEY từ biến môi trường.
# Có thể dùng khóa phát triển tạm thời khi chạy máy cá nhân.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-hulo-local-development-only-change-before-deploy'
)

DEBUG = True

ALLOWED_HOSTS = []


# 3. CÁC ỨNG DỤNG DJANGO
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # App dùng chung: tài khoản và phân quyền
    'accounts',

    # Module 1: Trung tâm hỗ trợ / FAQ
    'support',

    # Module 2: Chatbot
    'chatbot',

    # Module 3: Ticket Management & SLA
    'tickets',

    # Module 4: Xử lý khiếu nại
    'disputes',

    # Module 5: Customer 360, CSAT, Loyalty
    'customers',
]


# 4. MIDDLEWARE
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# 5. CẤU HÌNH URL
ROOT_URLCONF = 'config.urls'


# 6. CẤU HÌNH TEMPLATES
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        # Thư mục HTML dùng chung
        'DIRS': [
            BASE_DIR / 'templates',
        ],

        'APP_DIRS': True,

        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                # CRM HULO: nhận diện vai trò trên giao diện
                'accounts.context_processors.user_role',
            ],
        },
    },
]


# 7. CẤU HÌNH WSGI
WSGI_APPLICATION = 'config.wsgi.application'


# 8. CƠ SỞ DỮ LIỆU SQLITE
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# 9. KIỂM TRA MẬT KHẨU
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME':
        'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# 10. NGÔN NGỮ VÀ MÚI GIỜ
LANGUAGE_CODE = 'vi'

TIME_ZONE = 'Asia/Ho_Chi_Minh'

USE_I18N = True

USE_TZ = True


# 11. STATIC FILES: CSS, JAVASCRIPT, IMAGES
STATIC_URL = 'static/'

# ==========================================
# MEDIA FILES - LƯU TRỮ ẢNH VÀ TỆP ĐÍNH KÈM
# ==========================================

MEDIA_URL = '/media/'

# Giữ nguyên vị trí kho file hiện tại ở thư mục gốc dự án.
MEDIA_ROOT = BASE_DIR

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]


# 12. KIỂU KHÓA CHÍNH MẶC ĐỊNH
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
