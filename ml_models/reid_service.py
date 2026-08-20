"""
Goat Re-Identification Service

This module provides high-level functions for goat identification and matching
during AI monitoring. It never creates goat records — registration is manual only.
"""

import numpy as np
import logging
from typing import TYPE_CHECKING, List, Dict, Tuple, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from iot.goat_models import Goat


class GoatReIdentificationService:
    """Service for goat re-identification and matching"""
    
    def __init__(self, feature_extractor=None, similarity_threshold: float = 0.85):
        """
        Initialize re-identification service.
        
        Args:
            feature_extractor: FeatureExtractor instance (if None, will use global instance)
            similarity_threshold: Minimum similarity score for matching (0-1)
        """
        self.similarity_threshold = similarity_threshold
        
        # Lazy load feature extractor
        if feature_extractor is None:
            from .feature_extraction import get_global_feature_extractor
            self.feature_extractor = get_global_feature_extractor()
        else:
            self.feature_extractor = feature_extractor
        
        logger.info(f"GoatReIdentificationService initialized (threshold: {similarity_threshold})")
    
    def find_matching_goat(self, embedding: np.ndarray, 
                          confidence_threshold: Optional[float] = None) -> Optional[Tuple]:
        """
        Find the best matching goat for a given embedding.
        
        Args:
            embedding: Feature embedding vector to match
            confidence_threshold: Override default similarity threshold
            
        Returns:
            Tuple of (Goat object, similarity_score) if match found, None otherwise
        """
        from iot.goat_models import Goat
        
        threshold = confidence_threshold or self.similarity_threshold
        
        # Get all active goats with embeddings
        active_goats = Goat.objects.filter(
            status='active',
            feature_embedding__isnull=False
        )
        
        if not active_goats.exists():
            logger.info("No active goats with embeddings found")
            return None
        
        best_match = None
        best_similarity = 0.0
        
        # Compare with each goat's embedding
        for goat in active_goats:
            if goat.feature_embedding:
                # Calculate similarity
                similarity = self.feature_extractor.cosine_similarity(
                    embedding, 
                    np.array(goat.feature_embedding)
                )
                
                if similarity > best_similarity and similarity >= threshold:
                    best_similarity = similarity
                    best_match = goat
        
        if best_match:
            logger.info(f"Match found: {best_match.goat_id} (similarity: {best_similarity:.3f})")
            return (best_match, best_similarity)
        else:
            logger.info(f"No match found (best similarity: {best_similarity:.3f} < threshold: {threshold})")
            return None
    
    def generate_goat_id(self) -> str:
        """
        Generate a unique goat ID with auto-increment.
        
        Returns:
            Unique goat ID (e.g., "G001", "G002", etc.)
        """
        from iot.models import Goat
        
        # Find the highest existing goat ID number
        all_goats = Goat.objects.filter(goat_id__startswith='G').order_by('-goat_id')
        
        if all_goats.exists():
            # Extract number from last goat_id (e.g., "G025" -> 25)
            last_id = all_goats.first().goat_id
            try:
                last_number = int(last_id[1:])  # Skip 'G' prefix
                new_number = last_number + 1
            except ValueError:
                # If parsing fails, start from 1
                new_number = 1
        else:
            new_number = 1
        
        # Format as G001, G002, etc.
        new_id = f"G{new_number:03d}"
        
        # Ensure uniqueness (just in case)
        while Goat.objects.filter(goat_id=new_id).exists():
            new_number += 1
            new_id = f"G{new_number:03d}"
        
        return new_id

    def update_goat_embedding(self, goat: 'Goat', new_embedding: np.ndarray, 
                             weight: float = 0.3):
        """
        Update goat's embedding using exponential moving average.
        
        Args:
            goat: Goat object to update
            new_embedding: New embedding vector
            weight: Weight for new embedding (0-1), default 0.3 means 30% new, 70% old
        """
        if goat.feature_embedding:
            old_embedding = np.array(goat.feature_embedding)
            # Exponential moving average
            updated_embedding = (1 - weight) * old_embedding + weight * new_embedding
            # Re-normalize
            updated_embedding = updated_embedding / (np.linalg.norm(updated_embedding) + 1e-8)
        else:
            updated_embedding = new_embedding
        
        goat.update_embedding(updated_embedding)
        logger.info(f"Updated embedding for {goat.goat_id}")
    
    def process_detection(self, image: np.ndarray, detection: Dict, camera) -> Dict:
        """
        Process a single goat detection with re-identification.

        Unknown goats are recorded as unidentified detections. Registration is
        manual only — the AI system never creates goat records.

        Args:
            image: Full camera frame
            detection: Detection dict with bbox and confidence
            camera: IPCamera instance

        Returns:
            Dict with identification results
        """
        bbox = detection['bbox']
        detection_confidence = detection['confidence']
        
        # Extract crop
        x = int(bbox['x'])
        y = int(bbox['y'])
        w = int(bbox['width'])
        h = int(bbox['height'])
        crop = image[y:y+h, x:x+w]
        
        # Extract embedding
        embedding = self.feature_extractor.extract(crop)
        
        # Try to match with existing goat
        match_result = self.find_matching_goat(embedding)
        
        if match_result:
            # Known goat
            goat, similarity = match_result
            goat.update_last_seen()
            
            # Optionally update embedding (helps adapt to changes over time)
            # self.update_goat_embedding(goat, embedding, weight=0.1)
            
            result = {
                'goat_id': goat.goat_id,
                'goat': goat,
                'is_new': False,
                'similarity': similarity,
                'embedding': embedding.tolist(),
                'bbox': bbox,
                'detection_confidence': detection_confidence
            }
        else:
            # Unknown goat - recorded as an unidentified detection.
            # Registration is manual only; the AI system never creates goat records.
            result = {
                'goat_id': None,
                'goat': None,
                'is_new': True,
                'similarity': 0.0,
                'embedding': embedding.tolist(),
                'bbox': bbox,
                'detection_confidence': detection_confidence
            }
        
        # Save detection history
        if camera and result.get('goat') is not None:
            self.save_detection_history(result, camera, crop)
        
        return result
    
    def save_detection_history(self, result: Dict, camera, crop_image: np.ndarray):
        """Save detection to GoatDetectionHistory"""
        from iot.goat_models import GoatDetectionHistory
        from django.core.files.base import ContentFile
        import cv2
        
        if camera is None:
            return

        try:
            history = GoatDetectionHistory.objects.create(
                goat=result['goat'],
                camera=camera,
                bounding_box=result['bbox'],
                detection_confidence=result['detection_confidence'],
                identification_confidence=result['similarity'] if not result['is_new'] else 0.0,
                feature_embedding=result['embedding'],
                similarity_score=result['similarity'],
                is_new_goat=result['is_new']
            )
            
            # Save crop image
            _, img_encoded = cv2.imencode('.jpg', crop_image)
            img_bytes = img_encoded.tobytes()
            history.crop_image.save(
                f"detection_{history.id}.jpg",
                ContentFile(img_bytes),
                save=True
            )
            
        except Exception as e:
            logger.error(f"Failed to save detection history: {e}")
    
    def process_frame(self, image: np.ndarray, detections: List[Dict], camera) -> Dict:
        """
        Process all detections in a frame.

        Args:
            image: Full camera frame
            detections: List of detection dicts from YOLOv8
            camera: IPCamera instance

        Returns:
            Dict with all identification results
        """
        results = {
            'identified_goats': [],
            'new_goats': [],
            'total_count': len(detections),
            'timestamp': timezone.now()
        }

        for detection in detections:
            try:
                result = self.process_detection(image, detection, camera)
                
                if result['is_new']:
                    results['new_goats'].append(result)
                else:
                    results['identified_goats'].append(result)
                    
            except Exception as e:
                logger.error(f"Failed to process detection: {e}")
                continue
        
        logger.info(
            f"Processed {results['total_count']} detections: "
            f"{len(results['identified_goats'])} identified, "
            f"{len(results['new_goats'])} new"
        )
        
        return results


# Global service instance
_reid_service = None


def get_reid_service(similarity_threshold: float = 0.85) -> GoatReIdentificationService:
    """Get or create global re-identification service instance"""
    global _reid_service
    
    if _reid_service is None:
        _reid_service = GoatReIdentificationService(similarity_threshold=similarity_threshold)
    
    return _reid_service


def identify_goat_from_detection(image: np.ndarray, detection: Dict, camera) -> Dict:
    """
    Convenience function to identify a goat from a detection.
    
    Args:
        image: Full camera frame
        detection: Detection dict with bbox and confidence
        camera: IPCamera instance
        
    Returns:
        Dict with identification result
    """
    service = get_reid_service()
    return service.process_detection(image, detection, camera)


def identify_goats_from_frame(image: np.ndarray, detections: List[Dict], camera) -> Dict:
    """
    Convenience function to identify all goats in a frame.

    Args:
        image: Full camera frame
        detections: List of detection dicts from YOLOv8
        camera: IPCamera instance

    Returns:
        Dict with all identification results
    """
    service = get_reid_service()
    return service.process_frame(image, detections, camera)
