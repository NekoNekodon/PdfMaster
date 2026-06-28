from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('pdf_app.urls')),
    path("", TemplateView.as_view(template_name="index.html")),
]
# DEBUG=True 时依赖这行加载本地static目录
urlpatterns += staticfiles_urlpatterns()