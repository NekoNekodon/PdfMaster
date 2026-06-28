from django.db import models
from django.utils import timezone

class PdfTask(models.Model):
    file_name = models.CharField(max_length=255, verbose_name="原始文件名")
    start_page = models.IntegerField(verbose_name="起始页码")
    end_page = models.IntegerField(verbose_name="结束页码")
    create_time = models.DateTimeField(default=timezone.now, verbose_name="创建时间")
    status = models.CharField(max_length=30, default="success", verbose_name="处理状态")

    class Meta:
        verbose_name = "PDF拆分记录"
        verbose_name_plural = verbose_name