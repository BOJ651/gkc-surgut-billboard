from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from core.views import EventViewSet, RegistrationViewSet, upcoming_events, search_events

router = DefaultRouter()
router.register(r'events', EventViewSet, basename='event')
router.register(r'registrations', RegistrationViewSet, basename='registration')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('upcoming/', upcoming_events, name='upcoming_events'),
    path('search/', search_events, name='search_events'),
]