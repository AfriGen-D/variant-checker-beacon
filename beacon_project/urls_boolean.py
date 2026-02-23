"""
URL Configuration for Boolean Mode
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('beacon_api.urls_boolean')),
]
