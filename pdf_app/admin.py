from django.contrib import admin
from .models import PdfTask

@admin.register(PdfTask)
class PdfTaskAdmin(admin.ModelAdmin):
    list_display = ["id", "file_name", "start_page", "end_page", "status", "create_time"]
    list_filter = ["status"]
    search_fields = ["file_name"]