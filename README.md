
# CRM HULO – Hệ thống quản lý và chăm sóc khách hàng

## 1. Giới thiệu dự án

CRM HULO là website quản lý và chăm sóc khách hàng
dành cho doanh nghiệp HULO.

Dự án được xây dựng bằng:
- Python
- Django 5.2
- SQLite
- HTML, CSS, JavaScript

## 2. Cấu trúc hệ thống

| App | Chức năng |
|-----|-----------|
| accounts | Đăng nhập, đăng xuất, phân quyền |
| support | Module 1 – Help Center / FAQ |
| chatbot | Module 2 – Chatbot |
| tickets | Module 3 – Ticket Management & SLA |
| disputes | Module 4 – Phối hợp xử lý khiếu nại |
| customers | Module 5 – Customer 360°, CSAT & Loyalty |

Các thư mục dùng chung:
- config/: Cấu hình Django
- templates/: Giao diện HTML
- static/: CSS, JavaScript và hình ảnh

## 3. Hướng dẫn cài đặt dự án

### Bước 1: Tải dự án từ GitHub

git clone <LINK_REPOSITORY>

cd CRM_HULO

### Bước 2: Tạo môi trường ảo

python -m venv .venv

### Bước 3: Kích hoạt môi trường ảo

Windows PowerShell:

.\.venv\Scripts\Activate.ps1

Nếu PowerShell chặn kích hoạt, có thể dùng
CMD với lệnh:

.venv\Scripts\activate.bat

### Bước 4: Cài đặt thư viện

python -m pip install -r requirements.txt

### Bước 5: Cấu hình biến môi trường

Thiết lập DJANGO_SECRET_KEY riêng cho môi trường chạy.

Ví dụ trên PowerShell:

$env:DJANGO_SECRET_KEY = "KHOA_BI_MAT_RIENG_CUA_BAN"

Không đưa khóa bí mật thực tế lên GitHub.

### Bước 6: Tạo cơ sở dữ liệu

python manage.py migrate

### Bước 7: Tạo tài khoản quản trị

python manage.py createsuperuser

### Bước 8: Chạy website

python manage.py runserver

Truy cập:

http://127.0.0.1:8000/accounts/login/

## 4. Quy ước lập trình nhóm

- Mỗi thành viên phụ trách một module.
- Mỗi thành viên làm việc trên một Git branch riêng.
- Không tự ý chỉnh sửa các file dùng chung.
- Các trang HTML kế thừa templates/base.html.
- Sử dụng lại Models dùng chung, không tạo dữ liệu trùng.
- Kiểm tra quyền truy cập trong Django Views.
- Thống nhất trước khi chỉnh sửa Models và Migrations.
- Kiểm tra chức năng trước khi gửi Pull Request.

## 5. Quy ước dữ liệu

- accounts.Staff: Hồ sơ nhân viên
- customers.Customer: Hồ sơ khách hàng
- tickets.Ticket: Ticket do Module 3 quản lý

Module 4 và Module 5 sẽ tham chiếu Ticket từ Module 3.

Không tạo thêm bảng Customer, Staff hoặc Ticket trùng lặp.

## 6. Quy trình CRM HULO

Khách hàng
→ Help Center / FAQ
→ Chatbot
→ Tạo Ticket nếu chưa giải quyết được
→ Nhân viên CSKH tiếp nhận
→ Phối hợp chuyên môn khi cần
→ Cập nhật kết quả
→ Đánh giá CSAT
→ Chăm sóc khách hàng và Loyalty

## 7. Trạng thái dự án

Đã xây dựng nền tảng:
- Đăng nhập và đăng xuất
- Nhận diện vai trò người dùng
- Kiểm soát quyền truy cập cơ bản
- Giao diện chung base.html
- Bộ khung URL, View và Template cho 5 module

Các chức năng nghiệp vụ đang được phát triển.
