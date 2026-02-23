"""
Authentication URLs for GA4GH Beacon v2 API
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView
from . import authentication

urlpatterns = [
    # JWT Authentication endpoints
    path('login/', authentication.BeaconTokenObtainPairView.as_view(), name='auth_login'),
    path('refresh/', authentication.BeaconTokenRefreshView.as_view(), name='auth_refresh'),
    path('verify/', TokenVerifyView.as_view(), name='auth_verify'),
    path('register/', authentication.register, name='auth_register'),
    path('logout/', authentication.logout, name='auth_logout'),
    
    # User management endpoints
    path('profile/', authentication.profile, name='auth_profile'),
    path('change-password/', authentication.change_password, name='auth_change_password'),
]