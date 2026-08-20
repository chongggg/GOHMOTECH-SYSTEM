"""Browser views for BLE goat tracking."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import BLEBeacon


@login_required
def ble_tracking_dashboard(request):
    return render(
        request,
        'iot/ble_tracking_dashboard.html',
        {'page_title': 'Goat Tracking'},
    )


@login_required
def ble_find_goat(request, goat_id):
    beacon = get_object_or_404(
        BLEBeacon.objects.select_related('goat'),
        goat__goat_id=goat_id,
        enabled=True,
    )
    return render(
        request,
        'iot/ble_tracking_dashboard.html',
        {
            'page_title': f'Find Goat {beacon.goat.goat_id}',
            'focus_goat': beacon.goat,
            'focus_goat_id': beacon.goat.goat_id,
            'focus_beacon': beacon,
        },
    )
