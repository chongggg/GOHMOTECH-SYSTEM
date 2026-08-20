"""URL configuration for the security app."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'detections', views.PersonDetectionViewSet, basename='persondetection')

app_name = 'security'

urlpatterns = [
    # Tabbed Security page.
    path('', views.security_dashboard, name='dashboard'),
    # Single detection page (deep-link target for "open related event").
    path('detections/<int:pk>/', views.person_detection_detail,
         name='person_detection_detail'),
    # REST API.
    path('api/', include(router.urls)),
]
