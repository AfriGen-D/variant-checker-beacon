"""
JWT Authentication implementation for GA4GH Beacon v2 API
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
import logging

logger = logging.getLogger('beacon_api')


class BeaconTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token obtain view with Beacon-specific response format
    """
    
    @extend_schema(
        tags=['Authentication'],
        summary='Login to Beacon API',
        description='Authenticate with username and password to receive JWT tokens',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'description': 'Username or email'},
                    'password': {'type': 'string', 'format': 'password'},
                },
                'required': ['username', 'password']
            }
        },
        responses={
            200: OpenApiResponse(
                description='Login successful',
                response={
                    'type': 'object',
                    'properties': {
                        'access': {'type': 'string', 'description': 'Access token'},
                        'refresh': {'type': 'string', 'description': 'Refresh token'},
                        'user': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer'},
                                'username': {'type': 'string'},
                                'email': {'type': 'string'},
                            }
                        }
                    }
                }
            ),
            401: OpenApiResponse(description='Invalid credentials'),
        }
    )
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Add user information to response
            username = request.data.get('username')
            user = User.objects.get(username=username)
            response.data['user'] = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_staff': user.is_staff,
            }
            
            logger.info(f"User {username} logged in successfully")
        
        return response


class BeaconTokenRefreshView(TokenRefreshView):
    """
    Custom JWT token refresh view with Beacon-specific response format
    """
    
    @extend_schema(
        tags=['Authentication'],
        summary='Refresh access token',
        description='Use refresh token to obtain new access token',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'refresh': {'type': 'string', 'description': 'Refresh token'},
                },
                'required': ['refresh']
            }
        },
        responses={
            200: OpenApiResponse(
                description='Token refreshed successfully',
                response={
                    'type': 'object',
                    'properties': {
                        'access': {'type': 'string', 'description': 'New access token'},
                    }
                }
            ),
            401: OpenApiResponse(description='Invalid or expired refresh token'),
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(
    tags=['Authentication'],
    summary='Register new user',
    description='Create a new user account for Beacon API access',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'username': {'type': 'string', 'minLength': 3, 'maxLength': 150},
                'email': {'type': 'string', 'format': 'email'},
                'password': {'type': 'string', 'format': 'password', 'minLength': 8},
                'password_confirm': {'type': 'string', 'format': 'password'},
                'first_name': {'type': 'string', 'required': False},
                'last_name': {'type': 'string', 'required': False},
            },
            'required': ['username', 'email', 'password', 'password_confirm']
        }
    },
    responses={
        201: OpenApiResponse(
            description='User created successfully',
            response={
                'type': 'object',
                'properties': {
                    'user': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer'},
                            'username': {'type': 'string'},
                            'email': {'type': 'string'},
                        }
                    },
                    'access': {'type': 'string', 'description': 'Access token'},
                    'refresh': {'type': 'string', 'description': 'Refresh token'},
                }
            }
        ),
        400: OpenApiResponse(description='Validation error'),
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Register a new user and return JWT tokens
    """
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')
    password_confirm = request.data.get('password_confirm')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')
    
    # Validation
    errors = {}
    
    if not username:
        errors['username'] = 'Username is required'
    elif User.objects.filter(username=username).exists():
        errors['username'] = 'Username already exists'
    
    if not email:
        errors['email'] = 'Email is required'
    elif User.objects.filter(email=email).exists():
        errors['email'] = 'Email already registered'
    
    if not password:
        errors['password'] = 'Password is required'
    elif password != password_confirm:
        errors['password_confirm'] = 'Passwords do not match'
    else:
        try:
            validate_password(password)
        except ValidationError as e:
            errors['password'] = list(e.messages)
    
    if errors:
        return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
    
    # Create user
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        logger.info(f"New user registered: {username}")
        
        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return Response(
            {'error': 'Failed to create user'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Authentication'],
    summary='Logout user',
    description='Blacklist the refresh token to logout user',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'refresh': {'type': 'string', 'description': 'Refresh token to blacklist'},
            },
            'required': ['refresh']
        }
    },
    responses={
        200: OpenApiResponse(description='Logout successful'),
        400: OpenApiResponse(description='Invalid token'),
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def logout(request):
    """
    Logout user by blacklisting the refresh token
    """
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        logger.info("User logged out successfully")
        
        return Response(
            {'message': 'Logout successful'},
            status=status.HTTP_200_OK
        )
    except TokenError as e:
        return Response(
            {'error': 'Invalid token'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return Response(
            {'error': 'Logout failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Authentication'],
    summary='Get current user profile',
    description='Retrieve profile information for authenticated user',
    responses={
        200: OpenApiResponse(
            description='User profile',
            response={
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'username': {'type': 'string'},
                    'email': {'type': 'string'},
                    'first_name': {'type': 'string'},
                    'last_name': {'type': 'string'},
                    'is_staff': {'type': 'boolean'},
                    'is_active': {'type': 'boolean'},
                    'date_joined': {'type': 'string', 'format': 'date-time'},
                }
            }
        ),
        401: OpenApiResponse(description='Not authenticated'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    """
    Get current user profile
    """
    user = request.user
    
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_staff': user.is_staff,
        'is_active': user.is_active,
        'date_joined': user.date_joined.isoformat(),
    })


@extend_schema(
    tags=['Authentication'],
    summary='Change password',
    description='Change password for authenticated user',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'old_password': {'type': 'string', 'format': 'password'},
                'new_password': {'type': 'string', 'format': 'password', 'minLength': 8},
                'new_password_confirm': {'type': 'string', 'format': 'password'},
            },
            'required': ['old_password', 'new_password', 'new_password_confirm']
        }
    },
    responses={
        200: OpenApiResponse(description='Password changed successfully'),
        400: OpenApiResponse(description='Validation error'),
        401: OpenApiResponse(description='Not authenticated or wrong password'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change password for authenticated user
    """
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    new_password_confirm = request.data.get('new_password_confirm')
    
    errors = {}
    
    # Validate old password
    if not old_password:
        errors['old_password'] = 'Old password is required'
    elif not user.check_password(old_password):
        errors['old_password'] = 'Incorrect password'
    
    # Validate new password
    if not new_password:
        errors['new_password'] = 'New password is required'
    elif new_password != new_password_confirm:
        errors['new_password_confirm'] = 'Passwords do not match'
    elif new_password == old_password:
        errors['new_password'] = 'New password must be different from old password'
    else:
        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            errors['new_password'] = list(e.messages)
    
    if errors:
        return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
    
    # Change password
    user.set_password(new_password)
    user.save()
    
    logger.info(f"Password changed for user: {user.username}")
    
    return Response(
        {'message': 'Password changed successfully'},
        status=status.HTTP_200_OK
    )