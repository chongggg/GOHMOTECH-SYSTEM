"""
Automated Feeding Decision Engine
CORE INTELLIGENCE MODULE

This module implements context-aware automated feeding based on:
- Environmental triggers (drought, rain, temperature)
- Computer vision analysis (grass health)
- Machine learning detections (goat behavior)
"""

from django.utils import timezone
from django.db.models import Avg
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class FeedingDecisionEngine:
    """
    Central intelligence for automated feeding decisions
    
    Analyzes environmental conditions, grass health, and goat behavior
    to determine if feeding assistance is required.
    """
    
    # Thresholds for environmental triggers
    DROUGHT_TEMP_THRESHOLD = 32.0  # Celsius
    DROUGHT_HUMIDITY_THRESHOLD = 40.0  # Percent
    DROUGHT_SOIL_MOISTURE_THRESHOLD = 25.0  # Percent
    
    RAIN_HUMIDITY_THRESHOLD = 80.0  # Percent
    
    GRASS_HEALTH_POOR_THRESHOLD = 0.35  # 0-1 scale
    GRASS_HEALTH_FAIR_THRESHOLD = 0.50
    
    GOAT_ACTIVITY_LOW_THRESHOLD = 0.30  # 0-1 scale
    GRAZING_BEHAVIOR_LOW_THRESHOLD = 0.40
    
    def __init__(self):
        self.decision_log = []
    
    def should_activate_automated_feeding(self):
        """
        Main decision function
        
        Returns:
            tuple: (should_feed: bool, trigger_reason: str, environmental_data: dict)
        """
        # Check environmental triggers
        env_trigger, env_reason, env_data = self._check_environmental_triggers()
        if env_trigger:
            return True, env_reason, env_data
        
        # Check grass health
        grass_trigger, grass_reason, grass_data = self._check_grass_health()
        if grass_trigger:
            return True, grass_reason, grass_data
        
        # Check goat behavior (ML)
        behavior_trigger, behavior_reason, behavior_data = self._check_goat_behavior()
        if behavior_trigger:
            return True, behavior_reason, behavior_data
        
        # No triggers activated
        return False, None, {}
    
    def _check_environmental_triggers(self):
        """
        Check environmental conditions for feeding triggers
        
        Returns:
            tuple: (triggered: bool, reason: str, data: dict)
        """
        try:
            from iot.models import SensorReading
            
            # Get recent sensor readings (last 30 minutes)
            recent_cutoff = timezone.now() - timedelta(minutes=30)
            recent_readings = SensorReading.objects.filter(
                timestamp__gte=recent_cutoff
            )
            
            if not recent_readings.exists():
                logger.warning("No recent sensor readings available")
                return False, None, {}
            
            # Calculate averages
            avg_data = recent_readings.aggregate(
                avg_temp=Avg('temperature'),
                avg_humidity=Avg('humidity'),
                avg_soil_moisture=Avg('soil_moisture')
            )
            
            temp = avg_data['avg_temp'] or 0
            humidity = avg_data['avg_humidity'] or 0
            soil_moisture = avg_data['avg_soil_moisture'] or 0
            
            environmental_data = {
                'temperature_celsius': round(temp, 2),
                'humidity_percent': round(humidity, 2),
                'soil_moisture_percent': round(soil_moisture, 2),
            }
            
            # DROUGHT DETECTION
            if (temp > self.DROUGHT_TEMP_THRESHOLD and 
                humidity < self.DROUGHT_HUMIDITY_THRESHOLD):
                logger.info(f"Drought trigger: Temp={temp}°C, Humidity={humidity}%")
                return True, 'high_temp_low_humidity', environmental_data
            
            if soil_moisture < self.DROUGHT_SOIL_MOISTURE_THRESHOLD:
                logger.info(f"Low soil moisture trigger: {soil_moisture}%")
                return True, 'low_soil_moisture', environmental_data
            
            # RAINFALL DETECTION (adjust feeding)
            # Note: High humidity + recent rain = natural forage may be sufficient
            if humidity > self.RAIN_HUMIDITY_THRESHOLD:
                # This is informational - may adjust feeding amount, not cancel
                logger.info(f"High humidity detected: {humidity}% - Natural forage may be improved")
                # Not triggering feeding, but noting the condition
            
            return False, None, environmental_data
            
        except Exception as e:
            logger.error(f"Error checking environmental triggers: {e}")
            return False, None, {}
    
    def _check_grass_health(self):
        """
        Check grass health from computer vision analysis
        
        Returns:
            tuple: (triggered: bool, reason: str, data: dict)
        """
        try:
            from iot.goat_models import GrassHealthLog
            
            # Get most recent grass health analysis (last 2 hours)
            recent_cutoff = timezone.now() - timedelta(hours=2)
            recent_grass = GrassHealthLog.objects.filter(
                timestamp__gte=recent_cutoff
            ).order_by('-timestamp').first()
            
            if not recent_grass:
                logger.warning("No recent grass health data available")
                return False, None, {}
            
            grass_data = {
                'grass_health_index': round(recent_grass.greenness_index, 3),
                'health_status': recent_grass.health_status,
            }
            
            # POOR GRASS HEALTH
            if recent_grass.greenness_index < self.GRASS_HEALTH_POOR_THRESHOLD:
                logger.info(f"Poor grass health detected: {recent_grass.greenness_index:.2f}")
                return True, 'poor_grass_health', grass_data
            
            # DROUGHT STRESSED GRASS
            if recent_grass.is_drought_stressed:
                logger.info(f"Drought-stressed grass detected in {recent_grass.location}")
                return True, 'drought_detected', grass_data
            
            return False, None, grass_data
            
        except Exception as e:
            logger.error(f"Error checking grass health: {e}")
            return False, None, {}
    
    def _check_goat_behavior(self):
        """
        Check goat behavior patterns from ML detection
        
        Returns:
            tuple: (triggered: bool, reason: str, data: dict)
        """
        try:
            from iot.goat_models import GoatBehaviorLog
            
            # Get recent behavior logs (last 1 hour)
            recent_cutoff = timezone.now() - timedelta(hours=1)
            recent_behaviors = GoatBehaviorLog.objects.filter(
                timestamp__gte=recent_cutoff
            )
            
            if not recent_behaviors.exists():
                logger.warning("No recent behavior data available")
                return False, None, {}
            
            # Analyze behavior patterns
            total_detections = recent_behaviors.count()
            
            # Count inactive/abnormal behaviors
            inactive_count = recent_behaviors.filter(
                behavior_type__in=['inactive', 'abnormal', 'lying']
            ).count()
            
            grazing_count = recent_behaviors.filter(
                behavior_type='grazing'
            ).count()
            
            # Calculate scores
            activity_score = 1.0 - (inactive_count / total_detections) if total_detections > 0 else 1.0
            grazing_score = grazing_count / total_detections if total_detections > 0 else 1.0
            
            behavior_data = {
                'goat_activity_score': round(activity_score, 3),
                'grazing_behavior_score': round(grazing_score, 3),
            }
            
            # LOW ACTIVITY DURING FEEDING HOURS
            current_hour = timezone.now().hour
            if 6 <= current_hour <= 18:  # Daytime hours
                if activity_score < self.GOAT_ACTIVITY_LOW_THRESHOLD:
                    logger.info(f"Low activity detected during feeding hours: {activity_score:.2f}")
                    return True, 'inactive_goats', behavior_data
            
            # REDUCED GRAZING BEHAVIOR
            if grazing_score < self.GRAZING_BEHAVIOR_LOW_THRESHOLD:
                logger.info(f"Reduced grazing behavior detected: {grazing_score:.2f}")
                return True, 'reduced_grazing', behavior_data
            
            # ABNORMAL BEHAVIOR PATTERN
            abnormal_count = recent_behaviors.filter(
                behavior_type='abnormal'
            ).count()
            
            if abnormal_count > total_detections * 0.3:  # >30% abnormal
                logger.info(f"High rate of abnormal behavior: {abnormal_count}/{total_detections}")
                return True, 'abnormal_behavior', behavior_data
            
            return False, None, behavior_data
            
        except Exception as e:
            logger.error(f"Error checking goat behavior: {e}")
            return False, None, {}
    
    def execute_automated_feeding(self, feeder_device, trigger_reason, environmental_data):
        """
        Execute automated feeding and log the decision
        
        Args:
            feeder_device: Device instance (feeder)
            trigger_reason: str - reason code for feeding
            environmental_data: dict - snapshot of environmental/ML data
        
        Returns:
            FeedLog instance or None
        """
        try:
            from feeding.models import FeedLog
            
            # Calculate feed amount based on context
            base_amount = 500  # grams, base amount
            
            # Adjust amount based on trigger severity
            if trigger_reason in ['drought_detected', 'poor_grass_health']:
                feed_amount = base_amount * 1.5  # 50% more for severe conditions
            elif trigger_reason in ['low_soil_moisture', 'high_temp_low_humidity']:
                feed_amount = base_amount * 1.25  # 25% more
            else:
                feed_amount = base_amount
            
            # Create feed log with full context
            feed_log = FeedLog.objects.create(
                feeder=feeder_device,
                amount_dispensed=int(feed_amount),
                feeding_mode='automated',
                trigger_reason=trigger_reason,
                status='success',
                
                # Environmental snapshot
                temperature_celsius=environmental_data.get('temperature_celsius'),
                humidity_percent=environmental_data.get('humidity_percent'),
                soil_moisture_percent=environmental_data.get('soil_moisture_percent'),
                grass_health_index=environmental_data.get('grass_health_index'),
                
                # ML snapshot
                goat_activity_score=environmental_data.get('goat_activity_score'),
                grazing_behavior_score=environmental_data.get('grazing_behavior_score'),
            )
            
            logger.info(
                f"Automated feeding executed: {feed_amount}g dispensed. "
                f"Reason: {trigger_reason}"
            )
            
            # TODO: Send MQTT command to physical feeder device
            # self._send_feeder_command(feeder_device, feed_amount)
            
            return feed_log
            
        except Exception as e:
            logger.error(f"Error executing automated feeding: {e}")
            return None
    
    def _send_feeder_command(self, feeder_device, amount_grams):
        """
        Send command to physical feeder via MQTT
        
        TODO: Implement MQTT publishing
        """
        pass


def run_automated_feeding_check():
    """
    Periodic task to check if automated feeding should be triggered
    
    This should be called by Celery beat or cron job every 15-30 minutes
    """
    try:
        from iot.models import Device
        
        engine = FeedingDecisionEngine()
        
        # Check if feeding is needed
        should_feed, trigger_reason, env_data = engine.should_activate_automated_feeding()
        
        if should_feed:
            # Get active feeder device
            feeder = Device.objects.filter(
                device_type='feeder',
                is_active=True
            ).first()
            
            if feeder:
                logger.info(f"Automated feeding triggered: {trigger_reason}")
                engine.execute_automated_feeding(feeder, trigger_reason, env_data)
            else:
                logger.warning("No active feeder device found")
        else:
            logger.info("No automated feeding triggers activated")
            
    except Exception as e:
        logger.error(f"Error in automated feeding check: {e}")
