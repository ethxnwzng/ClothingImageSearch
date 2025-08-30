"""
Product Search Models Module

This module contains Django models that define the database schema for the Halara Image Search prototype.
It includes models for products, search sessions, search results, and YOLO detections.

The models are designed to store all data related to the image search functionality and provide
a foundation for tracking search history and results.
"""

from django.db import models
from django.utils import timezone
import uuid


class Product(models.Model):
    """
    Model to store product information and metadata.
    
    This model represents products that can be searched for using the image search system.
    It stores product details, S3 URLs for images, and metadata for categorization.
    
    params:
        id: UUID primary key for unique product identification
        product_code: Unique identifier for the product
        name: Human-readable product name
        description: Detailed product description
        category: Product category for organization
        s3_url: S3 URL where the product image is stored
        created_at: Timestamp when the product was created
        updated_at: Timestamp when the product was last updated
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product_code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    s3_url = models.URLField(max_length=500)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        """
        String representation of the product.
        
        returns:
            Formatted string containing product code and name
        """
        return f"{self.product_code} - {self.name}"


class SearchSession(models.Model):
    """
    Model to track individual search sessions and their metadata.
    
    This model represents a single search session initiated by a user.
    It stores the uploaded image, S3 URL, and links to all results from that search.
    
    params:
        id: UUID primary key for unique session identification
        session_id: Unique session identifier for external reference
        uploaded_image: Image file uploaded by the user
        s3_url: S3 URL where the uploaded image is stored
        created_at: Timestamp when the search session was created
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_id = models.CharField(max_length=100, unique=True)
    uploaded_image = models.ImageField(upload_to='uploads/')
    s3_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        """
        String representation of the search session.
        
        returns:
            Formatted string containing session ID and creation timestamp
        """
        return f"Session {self.session_id} - {self.created_at}"


class SearchResult(models.Model):
    """
    Model to store individual search results from various search algorithms.
    
    This model stores results from both DINO visual search and other search methods.
    It includes confidence scores, result types, and metadata from API responses.
    
    params:
        id: UUID primary key for unique result identification
        search_session: Foreign key to the associated search session
        product: Optional foreign key to a matched product
        confidence_score: Confidence score for the search result
        result_type: Type of search result (e.g., 'visual_search', 'yolo')
        metadata: JSON field storing additional API response data
        created_at: Timestamp when the result was created
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    search_session = models.ForeignKey(SearchSession, on_delete=models.CASCADE, related_name='results')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    confidence_score = models.FloatField()
    result_type = models.CharField(max_length=50)  # 'dino', 'yolo', 'combined'
    metadata = models.JSONField(default=dict)  # Store additional API response data
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        """
        String representation of the search result.
        
        returns:
            Formatted string containing session ID and confidence score
        """
        return f"Result for {self.search_session.session_id} - {self.confidence_score}"


class YOLODetection(models.Model):
    """
    Model to store YOLO object detection results and metadata.
    
    This model stores the results from YOLO object detection, including
    detected objects, bounding boxes, and output mask image URLs.
    
    params:
        id: UUID primary key for unique detection identification
        search_session: Foreign key to the associated search session
        detected_objects: JSON field storing YOLO detection results
        output_mask_urls: JSON field storing URLs to mask images
        created_at: Timestamp when the detection was created
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    search_session = models.ForeignKey(SearchSession, on_delete=models.CASCADE, related_name='yolo_detections')
    detected_objects = models.JSONField()  # Store boxes, phrases, scores
    output_mask_urls = models.JSONField(default=list)  # Store mask image URLs
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        """
        String representation of the YOLO detection.
        
        returns:
            Formatted string containing session ID for the detection
        """
        return f"YOLO Detection for {self.search_session.session_id}"
