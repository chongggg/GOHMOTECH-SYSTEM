"""
Celery tasks for ML Models

Background tasks for:
- Batch ML inference processing
- Model training/fine-tuning (future)
- Detection data cleanup
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def process_pending_detections():
    """
    Process any pending detection images.
    Useful for batch processing or retry logic.
    """
    from .models import Detection
    from .ml_utils import get_detector
    
    pending = Detection.objects.filter(processed=False)
    
    if not pending.exists():
        return "No pending detections"
    
    detector = get_detector()
    if not detector:
        logger.error("No active ML model found")
        return "No active model"
    
    processed_count = 0
    for detection in pending:
        try:
            # Mark as processed
            detection.processed = True
            detection.save()
            processed_count += 1
        except Exception as e:
            logger.error(f"Error processing detection {detection.id}: {e}")
    
    return f"Processed {processed_count} detections"


@shared_task
def cleanup_old_detections(days=30):
    """
    Clean up old detection records to save database space.
    
    Args:
        days: Number of days to keep (default: 30)
    """
    from .models import Detection
    
    cutoff_date = timezone.now() - timedelta(days=days)
    old_detections = Detection.objects.filter(timestamp__lt=cutoff_date)
    
    count = old_detections.count()
    old_detections.delete()
    
    logger.info(f"Cleaned up {count} old detections")
    return f"Deleted {count} detections older than {days} days"


@shared_task
def generate_detection_report(start_date, end_date):
    """
    Generate a detection summary report for a date range.
    
    Args:
        start_date: Start date (ISO format string)
        end_date: End date (ISO format string)
    """
    from .models import Detection
    from django.db.models import Count, Avg, Sum
    from datetime import datetime
    
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    
    detections = Detection.objects.filter(
        timestamp__gte=start,
        timestamp__lte=end
    )
    
    stats = {
        'total_detections': detections.count(),
        'total_goats': detections.aggregate(total=Sum('goat_count'))['total'] or 0,
        'average_confidence': detections.aggregate(avg=Avg('confidence'))['avg'] or 0,
        'cameras': detections.values('camera__name').annotate(count=Count('id')),
    }
    
    logger.info(f"Generated detection report: {stats}")
    return stats
