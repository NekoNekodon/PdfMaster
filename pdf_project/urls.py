from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('pdf_app.urls')),
    # 匹配根路径 /，渲染 templates/index.html
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
]

# 本地开发静态文件支持（DEBUG=True才生效）
urlpatterns += staticfiles_urlpatterns()