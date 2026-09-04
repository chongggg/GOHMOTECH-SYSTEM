"""
Reports module — views.

The Reports module presents a Report Center (landing page of report cards) and a
single generic report page that renders any report type from the uniform
``ReportData`` produced by ``analytics.report_data``. Exports (CSV / Excel) and
the print-friendly view are served from the same data, guaranteeing that the
screen, the print-out and the downloaded file always agree.
"""

from django.shortcuts import render
from django.http import Http404
from django.urls import reverse
from rest_framework import viewsets
from marketplace.decorators import farm_owner_required
from marketplace.permissions import IsFarmOwnerOrAdmin

from .models import Report
from .serializers import ReportSerializer
from . import report_data
from .exports import export_report


class ReportViewSet(viewsets.ModelViewSet):
    """ViewSet for saved Report metadata (CRUD via the API)."""
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsFarmOwnerOrAdmin]

    def perform_create(self, serializer):
        serializer.save(generated_by=self.request.user)


@farm_owner_required
def report_center_view(request):
    """Landing page: a card per available report, grouped by category."""
    categories = {}
    for key, meta in report_data.REPORTS.items():
        card = {"key": key, "url": reverse(f"analytics:report_{key}"), **meta}
        categories.setdefault(meta["category"], []).append(card)

    context = {
        "categories": categories,
        "summary": report_data.build_center_summary(),
        "system_name": report_data.SYSTEM_NAME,
        "page_title": "Report Center",
    }
    return render(request, "analytics/report_center.html", context)


@farm_owner_required
def report_view(request, report_type):
    """Render a single report (any type) using the generic report template."""
    if report_type not in report_data.REPORTS:
        raise Http404("Unknown report type")

    try:
        data = report_data.build_report(report_type, request.GET)
    except ValueError as exc:
        if str(exc) == f"Unknown report type: {report_type}":
            raise Http404("Unknown report type")
        raise

    context = {
        "report": data,
        "report_type": report_type,
        "print_url": reverse(f"analytics:report_{report_type}_print"),
        "export_url": reverse(f"analytics:report_{report_type}_export"),
        "page_title": data["title"],
    }
    return render(request, "analytics/report_detail.html", context)


@farm_owner_required
def report_print_view(request, report_type):
    """Print-optimised, standalone version of a report (browser Save-as-PDF)."""
    if report_type not in report_data.REPORTS:
        raise Http404("Unknown report type")

    try:
        data = report_data.build_report(report_type, request.GET)
    except ValueError as exc:
        if str(exc) == f"Unknown report type: {report_type}":
            raise Http404("Unknown report type")
        raise

    context = {"report": data, "report_type": report_type}
    return render(request, "analytics/report_print.html", context)


@farm_owner_required
def report_export_view(request, report_type):
    """Download a report as CSV or Excel (?format=csv|xlsx)."""
    if report_type not in report_data.REPORTS:
        raise Http404("Unknown report type")

    try:
        data = report_data.build_report(report_type, request.GET)
    except ValueError as exc:
        if str(exc) == f"Unknown report type: {report_type}":
            raise Http404("Unknown report type")
        raise

    fmt = request.GET.get("format", "csv").lower()
    try:
        return export_report(data, fmt)
    except ValueError:
        raise Http404("Unsupported export format")
