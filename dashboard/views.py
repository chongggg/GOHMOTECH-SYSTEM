from django.shortcuts import render, redirect
from django.db.models import Count
from iot.models import Device
from ml_models.models import Detection
from feeding.models import FeedLog
from marketplace.auth import has_farm_access
from marketplace.decorators import farm_access_required


def dashboard_home_view(request):
    """Send public visitors and signed-in users to the right experience."""
    if not request.user.is_authenticated:
        return redirect('/marketplace/')
    if not has_farm_access(request.user):
        return redirect('/marketplace/')
    if request.user.is_staff or request.user.is_superuser:
        return redirect('/iot/')
    return redirect('/iot/owner/')


def permission_denied_view(request, exception=None):
    return render(request, '403.html', status=403)


@farm_access_required
def new_features_view(request):
    """New features guide page"""
    return render(request, 'dashboard/new_features.html', {
        'page_title': 'New Features Guide'
    })


@farm_access_required
def overview_view(request):
    """System overview page"""
    devices = Device.objects.filter(is_active=True)
    
    # Group devices by type
    devices_by_type = devices.values('device_type').annotate(count=Count('id'))
    
    # Recent activity
    recent_detections = Detection.objects.select_related('camera').order_by('-timestamp')[:10]
    recent_feeds = FeedLog.objects.select_related('feeder').order_by('-timestamp')[:10]
    
    context = {
        'devices': devices,
        'devices_by_type': devices_by_type,
        'recent_detections': recent_detections,
        'recent_feeds': recent_feeds,
        'page_title': 'System Overview'
    }
    
    return render(request, 'dashboard/overview.html', context)


@farm_access_required
def farm_map_view(request):
    """Farm map visualization page"""
    devices = Device.objects.filter(is_active=True)
    
    # Group devices by location
    devices_with_location = devices.exclude(location='')
    
    context = {
        'devices': devices_with_location,
        'page_title': 'Farm Map'
    }
    
    return render(request, 'dashboard/farm_map.html', context)
