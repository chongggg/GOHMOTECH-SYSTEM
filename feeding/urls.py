from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# API Router
router = DefaultRouter()
router.register(r'config', views.AutomatedFeedingConfigViewSet, basename='config')
router.register(r'schedules', views.FeedScheduleViewSet, basename='feedschedule')
router.register(r'levels', views.FeedLevelViewSet, basename='feedlevel')
router.register(r'logs', views.FeedLogViewSet, basename='feedlog')

app_name = 'feeding'

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Web pages (Django templates)
    path('', views.feeding_dashboard_view, name='dashboard'),
    path('schedules/', views.schedule_list_view, name='schedule_list'),
    path('logs/', views.feed_logs_view, name='feed_logs'),
]
