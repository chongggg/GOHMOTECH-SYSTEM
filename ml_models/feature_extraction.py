"""
Goat Re-Identification Module

This module provides feature extraction and similarity matching for individual goat identification.
Uses deep learning embeddings (MobileNetV2/ResNet50) to create unique feature vectors for each goat.
"""

import numpy as np
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Check available libraries
try:
    import torch
    import torchvision.models as models
    import torchvision.transforms as transforms
    from PIL import Image
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available. Install with: pip install torch torchvision")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not available. Install with: pip install opencv-python")


class FeatureExtractor:
    """Base class for feature extraction"""
    
    def __init__(self, model_name: str = 'mobilenet_v2', use_gpu: bool = False):
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.model = None
        self.transform = None
        self.device = None
        
    def extract(self, image: np.ndarray) -> np.ndarray:
        """
        Extract feature embedding from image.
        
        Args:
            image: Input image (BGR format from OpenCV or RGB from PIL)
            
        Returns:
            Feature embedding vector (numpy array)
        """
        raise NotImplementedError
    
    def extract_from_crop(self, image: np.ndarray, bbox: Dict) -> np.ndarray:
        """
        Extract features from a cropped region of the image.
        
        Args:
            image: Full image
            bbox: Bounding box dict with keys: x, y, width, height
            
        Returns:
            Feature embedding vector
        """
        x = int(bbox['x'])
        y = int(bbox['y'])
        w = int(bbox['width'])
        h = int(bbox['height'])
        
        # Crop image
        crop = image[y:y+h, x:x+w]
        
        # Extract features
        return self.extract(crop)
    
    @staticmethod
    def cosine_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score (0-1, where 1 is identical)
        """
        # Ensure inputs are numpy arrays
        if isinstance(embedding1, list):
            embedding1 = np.array(embedding1)
        if isinstance(embedding2, list):
            embedding2 = np.array(embedding2)
        
        # Normalize vectors
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # Calculate cosine similarity
        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
        
        # Clip to [0, 1] range
        return float(np.clip(similarity, 0, 1))
    
    @staticmethod
    def euclidean_distance(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate Euclidean distance between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Distance (lower is more similar)
        """
        if isinstance(embedding1, list):
            embedding1 = np.array(embedding1)
        if isinstance(embedding2, list):
            embedding2 = np.array(embedding2)
        
        return float(np.linalg.norm(embedding1 - embedding2))


class MobileNetV2FeatureExtractor(FeatureExtractor):
    """
    Feature extractor using MobileNetV2 (pretrained on ImageNet).
    
    Lightweight and fast - ideal for Raspberry Pi deployment.
    Output: 1280-dimensional feature vector
    """
    
    def __init__(self, use_gpu: bool = False, output_dim: int = 128):
        super().__init__('mobilenet_v2', use_gpu)
        
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required. Install with: pip install torch torchvision")
        
        self.output_dim = output_dim
        
        # Set device
        if use_gpu and torch.cuda.is_available():
            self.device = torch.device('cuda')
            logger.info("Using GPU for feature extraction")
        else:
            self.device = torch.device('cpu')
            logger.info("Using CPU for feature extraction")
        
        # Load pretrained MobileNetV2
        logger.info("Loading MobileNetV2 model...")
        mobilenet = models.mobilenet_v2(pretrained=True)
        
        # Remove classification head - keep only feature extractor
        # MobileNetV2 features output: (batch_size, 1280, 7, 7)
        self.model = torch.nn.Sequential(
            mobilenet.features,
            torch.nn.AdaptiveAvgPool2d((1, 1)),  # Global average pooling -> (batch, 1280, 1, 1)
            torch.nn.Flatten()  # Flatten to (batch, 1280)
        )
        
        # Optional: Add dimensionality reduction layer
        if output_dim != 1280:
            self.model = torch.nn.Sequential(
                self.model,
                torch.nn.Linear(1280, output_dim),
                torch.nn.ReLU()
            )
        
        self.model = self.model.to(self.device)
        self.model.eval()  # Set to evaluation mode
        
        # Define image preprocessing
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),  # MobileNetV2 input size
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],  # ImageNet mean
                std=[0.229, 0.224, 0.225]    # ImageNet std
            )
        ])
        
        logger.info(f"✅ MobileNetV2 loaded (output_dim: {self.output_dim})")
    
    def extract(self, image: np.ndarray) -> np.ndarray:
        """
        Extract feature embedding from image.
        
        Args:
            image: Input image (BGR format from OpenCV or RGB numpy array)
            
        Returns:
            Feature embedding vector (numpy array of shape (output_dim,))
        """
        try:
            # Convert BGR to RGB if needed (OpenCV uses BGR)
            if len(image.shape) == 3 and image.shape[2] == 3:
                # Check if it's BGR (OpenCV format)
                if isinstance(image, np.ndarray):
                    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if CV2_AVAILABLE else image
                else:
                    image_rgb = image
            else:
                image_rgb = image
            
            # Convert to PIL Image
            pil_image = Image.fromarray(image_rgb.astype(np.uint8))
            
            # Apply transforms
            input_tensor = self.transform(pil_image)
            input_batch = input_tensor.unsqueeze(0).to(self.device)  # Add batch dimension
            
            # Extract features
            with torch.no_grad():
                embedding = self.model(input_batch)
            
            # Convert to numpy
            embedding_np = embedding.cpu().numpy().squeeze()
            
            # Normalize embedding (L2 normalization)
            embedding_np = embedding_np / (np.linalg.norm(embedding_np) + 1e-8)
            
            return embedding_np
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            raise


class ResNet50FeatureExtractor(FeatureExtractor):
    """
    Feature extractor using ResNet50 (pretrained on ImageNet).
    
    More accurate than MobileNetV2 but slower.
    Output: 2048-dimensional feature vector (can be reduced)
    """
    
    def __init__(self, use_gpu: bool = False, output_dim: int = 128):
        super().__init__('resnet50', use_gpu)
        
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required. Install with: pip install torch torchvision")
        
        self.output_dim = output_dim
        
        # Set device
        if use_gpu and torch.cuda.is_available():
            self.device = torch.device('cuda')
            logger.info("Using GPU for feature extraction")
        else:
            self.device = torch.device('cpu')
            logger.info("Using CPU for feature extraction")
        
        # Load pretrained ResNet50
        logger.info("Loading ResNet50 model...")
        resnet = models.resnet50(pretrained=True)
        
        # Remove classification head - keep only feature extractor
        # ResNet50 features output: (batch_size, 2048)
        self.model = torch.nn.Sequential(*list(resnet.children())[:-1])  # Remove FC layer
        
        # Add flatten and optional dimensionality reduction
        if output_dim != 2048:
            self.model = torch.nn.Sequential(
                self.model,
                torch.nn.Flatten(),
                torch.nn.Linear(2048, output_dim),
                torch.nn.ReLU()
            )
        else:
            self.model = torch.nn.Sequential(
                self.model,
                torch.nn.Flatten()
            )
        
        self.model = self.model.to(self.device)
        self.model.eval()
        
        # Define image preprocessing
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
        
        logger.info(f"✅ ResNet50 loaded (output_dim: {self.output_dim})")
    
    def extract(self, image: np.ndarray) -> np.ndarray:
        """Extract feature embedding from image"""
        try:
            # Convert BGR to RGB if needed
            if len(image.shape) == 3 and image.shape[2] == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if CV2_AVAILABLE else image
            else:
                image_rgb = image
            
            # Convert to PIL Image
            pil_image = Image.fromarray(image_rgb.astype(np.uint8))
            
            # Apply transforms
            input_tensor = self.transform(pil_image)
            input_batch = input_tensor.unsqueeze(0).to(self.device)
            
            # Extract features
            with torch.no_grad():
                embedding = self.model(input_batch)
            
            # Convert to numpy
            embedding_np = embedding.cpu().numpy().squeeze()
            
            # Normalize embedding (L2 normalization)
            embedding_np = embedding_np / (np.linalg.norm(embedding_np) + 1e-8)
            
            return embedding_np
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            raise


def get_feature_extractor(model_type: str = 'mobilenet_v2', use_gpu: bool = False, output_dim: int = 128) -> FeatureExtractor:
    """
    Factory function to get appropriate feature extractor.
    
    Args:
        model_type: 'mobilenet_v2' or 'resnet50'
        use_gpu: Whether to use GPU acceleration
        output_dim: Output embedding dimension
        
    Returns:
        FeatureExtractor instance
    """
    model_type = model_type.lower()
    
    if model_type == 'mobilenet_v2':
        return MobileNetV2FeatureExtractor(use_gpu=use_gpu, output_dim=output_dim)
    elif model_type == 'resnet50':
        return ResNet50FeatureExtractor(use_gpu=use_gpu, output_dim=output_dim)
    else:
        raise ValueError(f"Unsupported model type: {model_type}. Choose 'mobilenet_v2' or 'resnet50'")


# Global feature extractor instance (lazy loaded)
_feature_extractor = None


def get_global_feature_extractor(model_type: str = 'mobilenet_v2') -> FeatureExtractor:
    """
    Get or create global feature extractor instance.
    
    Args:
        model_type: 'mobilenet_v2' or 'resnet50' (default: 'mobilenet_v2')
        
    Returns:
        Global FeatureExtractor instance
    """
    global _feature_extractor
    
    if _feature_extractor is None:
        # Default: MobileNetV2 with 128-dim output (best for Raspberry Pi)
        _feature_extractor = get_feature_extractor(
            model_type=model_type,
            use_gpu=False,  # Set to True if you have GPU
            output_dim=128
        )
    
    return _feature_extractor


def set_global_feature_extractor(model_type: str = 'mobilenet_v2', use_gpu: bool = False, output_dim: int = 128):
    """
    Set/reset the global feature extractor instance.
    
    Args:
        model_type: 'mobilenet_v2' or 'resnet50'
        use_gpu: Whether to use GPU
        output_dim: Output embedding dimension
    """
    global _feature_extractor
    _feature_extractor = get_feature_extractor(model_type, use_gpu, output_dim)


def extract_embedding(image: np.ndarray, bbox: Optional[Dict] = None) -> np.ndarray:
    """
    Convenience function to extract embedding from image or crop.
    
    Args:
        image: Input image
        bbox: Optional bounding box to crop first
        
    Returns:
        Feature embedding vector
    """
    extractor = get_global_feature_extractor()
    
    if bbox:
        return extractor.extract_from_crop(image, bbox)
    else:
        return extractor.extract(image)


def compare_embeddings(embedding1: np.ndarray, embedding2: np.ndarray, 
                       method: str = 'cosine') -> float:
    """
    Compare two embeddings and return similarity score.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        method: 'cosine' or 'euclidean'
        
    Returns:
        Similarity score (higher is more similar for cosine, lower for euclidean)
    """
    if method == 'cosine':
        return FeatureExtractor.cosine_similarity(embedding1, embedding2)
    elif method == 'euclidean':
        return FeatureExtractor.euclidean_distance(embedding1, embedding2)
    else:
        raise ValueError(f"Unsupported comparison method: {method}")

