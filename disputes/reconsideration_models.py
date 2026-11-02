from django.db import models


class ReconsiderationRecord(models.Model):
    TRANG_THAI_CHOICES = [
        ("DANG_XEM_XET", "Đang xem xét"),
        ("DA_LAP_PHUONG_AN", "Đã lập phương án điều chỉnh"),
        ("DA_KET_THUC", "Đã có kết quả xem xét"),
    ]

    ma_ho_so = models.ForeignKey(
        "disputes.DisputeCase",
        on_delete=models.PROTECT,
        related_name="cac_lan_xem_xet_lai",
        verbose_name="Hồ sơ thẩm định",
    )

    phuong_an_truoc = models.ForeignKey(
        "disputes.CompensationAction",
        on_delete=models.PROTECT,
        related_name="cac_lan_bi_yeu_cau_xem_xet",
        verbose_name="Phương án trước",
    )

    phuong_an_moi = models.OneToOneField(
        "disputes.CompensationAction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lan_xem_xet_tao_phuong_an",
        verbose_name="Phương án điều chỉnh",
    )

    nguoi_tiep_nhan = models.ForeignKey(
        "accounts.Staff",
        on_delete=models.PROTECT,
        related_name="cac_lan_tiep_nhan_xem_xet_lai",
        limit_choices_to={"vai_tro": "ASSESSOR"},
        verbose_name="Nhân viên tiếp nhận",
    )

    # Lưu lại phản hồi của khách tại thời điểm tiếp nhận.
    thoi_diem_phan_hoi = models.DateTimeField(
        verbose_name="Thời điểm khách phản hồi",
    )

    ly_do_khach_hang = models.TextField(
        verbose_name="Lý do khách không đồng ý",
    )

    noi_dung_tiep_nhan = models.TextField(
        verbose_name="Nội dung tiếp nhận xem xét lại",
    )

    ket_qua_xem_xet = models.TextField(
        blank=True,
        verbose_name="Kết quả xem xét lại",
    )

    nguoi_ket_thuc = models.ForeignKey(
        "accounts.Staff",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cac_lan_ket_thuc_xem_xet_lai",
        limit_choices_to={"vai_tro": "ASSESSOR"},
        verbose_name="Nhân viên ghi nhận kết quả",
    )

    thoi_diem_ket_thuc = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Thời điểm ghi nhận kết quả",
    )

    trang_thai = models.CharField(
        max_length=30,
        choices=TRANG_THAI_CHOICES,
        default="DANG_XEM_XET",
        verbose_name="Trạng thái",
    )

    thoi_diem_tao = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Lần xem xét lại hồ sơ"
        verbose_name_plural = "Các lần xem xét lại hồ sơ"
        ordering = ["-thoi_diem_tao"]

        constraints = [
            models.UniqueConstraint(
                fields=["ma_ho_so", "thoi_diem_phan_hoi"],
                name="disputes_reconsider_feedback_unique",
            ),
            models.UniqueConstraint(
                fields=["ma_ho_so"],
                condition=models.Q(trang_thai="DANG_XEM_XET"),
                name="disputes_reconsider_one_open",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        trang_thai="DANG_XEM_XET",
                        phuong_an_moi__isnull=True,
                        ket_qua_xem_xet="",
                        nguoi_ket_thuc__isnull=True,
                        thoi_diem_ket_thuc__isnull=True,
                    )
                    | models.Q(
                        trang_thai="DA_LAP_PHUONG_AN",
                        phuong_an_moi__isnull=False,
                        ket_qua_xem_xet="",
                        nguoi_ket_thuc__isnull=True,
                        thoi_diem_ket_thuc__isnull=True,
                    )
                    | (
                        models.Q(
                            trang_thai="DA_KET_THUC",
                            phuong_an_moi__isnull=True,
                            nguoi_ket_thuc__isnull=False,
                            thoi_diem_ket_thuc__isnull=False,
                        )
                        & ~models.Q(ket_qua_xem_xet="")
                    )
                ),
                name="disputes_reconsider_state_valid",
            ),
        ]

    def __str__(self):
        return (
            f"Hồ sơ #{self.ma_ho_so_id} - "
            f"Xem xét lại #{self.pk}"
        )