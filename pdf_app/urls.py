from django.urls import path
from . import views

urlpatterns = [
    path("split_extract/", views.SplitPdfView.as_view(), name="split_extract"),
    path("split_all_zip/", views.SplitAllPageZipView.as_view(), name="split_all_zip"),
    path("remove-keyword/", views.RemoveKeywordView.as_view(), name='remove_keyword'),
    path("merge/", views.MergeAllView.as_view(), name='merge'),
    path("toimg/", views.PdfToImageView.as_view(), name='pdftoimg'),
]