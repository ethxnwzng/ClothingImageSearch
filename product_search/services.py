"""
Product Search Services Module

This module contains service classes that handle external API interactions for the Halara Image Search prototype.
It provides services for S3 file storage, YOLO object detection, and DINO visual search functionality.

The services are designed to work with AWS infrastructure and integrate with the team's existing API endpoints.
"""

import requests
import json
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import logging
import os
import uuid
from .models import Product, SearchSession, SearchResult, YOLODetection

logger = logging.getLogger(__name__)


class S3Service:
    """
    Service class for handling AWS S3 operations including file uploads and storage management.
    
    This service provides a clean interface for uploading images to S3 and generating S3 URLs
    that can be used by other services like YOLO and DINO APIs.
    
    params:
        s3_client: boto3 S3 client instance configured with AWS credentials
        bucket_name: Name of the S3 bucket for storing uploaded images
    """
    
    def __init__(self):
        """Initialize S3 client with AWS credentials from Django settings."""
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket_name = settings.S3_BUCKET_NAME
    
    def upload_file(self, file_path, s3_key):
        """
        Upload a file from local filesystem to S3 bucket.
        
        params:
            file_path: Local path to the file to upload
            s3_key: S3 object key (path within bucket)
            
        returns:
            S3 URL string in format s3://bucket-name/key
        """
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            return f"s3://{self.bucket_name}/{s3_key}"
        except Exception as e:
            logger.error(f"Error uploading to S3: {e}")
            raise
    
    def upload_fileobj(self, file_obj, s3_key):
        """
        Upload a file object (like Django UploadedFile) to S3 bucket.
        
        This method follows Luke's implementation pattern:
        1. Uses test/ folder structure
        2. Sets proper content type for images
        3. Handles file objects correctly
        
        params:
            file_obj: File-like object to upload (e.g., Django UploadedFile)
            s3_key: S3 object key (path within bucket)
            
        returns:
            S3 URL string in format s3://bucket-name/key
        """
        try:
            #determine content type based on file extension
            file_type = s3_key.split('.')[-1].lower()
            content_type = f'image/{file_type}'
            
            #upload with proper content type
            self.s3_client.upload_fileobj(
                file_obj, 
                self.bucket_name, 
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )
            return f"s3://{self.bucket_name}/{s3_key}"
        except Exception as e:
            logger.error(f"Error uploading file object to S3: {e}")
            raise
    
    def upload_image(self, uploaded_file):
        """
        Upload an image file to S3 using the team lead's pattern.
        
        This method follows the exact pattern from the team lead's code:
        - Uses test/ folder structure
        - Extracts filename from uploaded file
        - Sets proper content type
        
        params:
            uploaded_file: Django UploadedFile object
            
        returns:
            S3 URL string in format s3://bucket-name/key
        """
        try:
            # Extract filename from uploaded file 
            filename = uploaded_file.name.split("/")[-1]
            
            # Use test/ folder structure 
            s3_key = f'test/{filename}'
            
            # Determine content type
            file_type = filename.split('.')[-1].lower()
            content_type = f'image/{file_type}'
            
            # Reset file pointer to beginning (Django UploadedFile needs this)
            uploaded_file.seek(0)
            
            # Upload with proper content type - exactly like test script
            self.s3_client.upload_fileobj(
                uploaded_file, 
                self.bucket_name, 
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )
            
            s3_url = f"s3://{self.bucket_name}/{s3_key}"
            return s3_url
            
        except Exception as e:
            logger.error(f"Error uploading image to S3: {e}")
            raise


class VisualSearchService:
    """
    Service class for handling DINO (Dense Image-to-Image Network) visual search API calls.
    
    This service provides methods to search for visually similar images using the team's
    DINO implementation. It handles authentication and API communication with the
    Visual Search API Gateway.
    
    params:
        base_url: Base URL for the Visual Search API
        session: requests.Session instance for making HTTP requests
    """
    
    def __init__(self):
        """Initialize Visual Search service with API URL from Django settings."""
        self.base_url = settings.VISUAL_SEARCH_API_URL
        logger.info(f"VisualSearchService initialized with URL: {self.base_url}")
        self.session = requests.Session()
    
    def test_connection(self, s3_url):
        """
        Test the connection to the Visual Search API with a sample S3 URL.
        
        params:
            s3_url: S3 URL to use for testing the API connection
            
        returns:
            JSON response from the API test endpoint
        """
        try:
            url = f"{self.base_url}/vis-search/test?s3url={s3_url}"
            #try without any special headers first
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error testing Visual Search API connection: {e}")
            raise
    
    def list_indexes(self):
        """
        Retrieve list of available search indexes from the Visual Search API.
        
        returns:
            JSON response containing list of available indexes
        """
        try:
            url = f"{self.base_url}/vis-search/index/list"
            #use simple json headers like the team lead's code
            headers = {'Content-Type': 'application/json'}
            response = self.session.post(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error listing indexes: {e}")
            raise
    
    def search(self, index_name, s3_url, k=5, scale=10):
        """
        Search for visually similar images using the DINO visual search API.
        
        This method constructs the API URL using the team lead's working approach
        and searches for similar images in the specified index.
        
        params:
            index_name: Name of the search index to use
            s3_url: S3 URL of the image to search for similar images
            k: Number of similar images to return (default: 5)
            scale: Scale factor for the search (default: 10)
            
        returns:
            JSON response containing similar image results
        """
        try:
            # Extract S3 key from the full S3 URL to match the working test script approach
            bucket, key = parse_s3_url(s3_url)
            if not bucket or not key:
                raise ValueError(f"Invalid S3 URL format: {s3_url}")
            
            # Use the exact same URL construction as the working test script
            url = f"{self.base_url}/vis-search/search/{index_name}?s3_url=s3://{bucket}/{key}&k={k}&scale={scale}"
            
            # Use a fresh requests session like the test script
            response = requests.get(url, timeout=30)
            
            logger.info(f"Visual Search API call: {url}")
            logger.info(f"Visual Search API response status: {response.status_code}")
            logger.info(f"Visual Search API response text: {response.text[:500]}...")  # Log first 500 chars
            
            response.raise_for_status()
            return response.json()
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Visual Search API connection error: {e}")
            return {
                "error": f"Visual Search API connection error: {str(e)}",
                "status": "connection_error"
            }
        except Exception as e:
            logger.error(f"Unexpected error in Visual Search: {e}")
            return {
                "error": f"Unexpected error in Visual Search: {str(e)}",
                "status": "error"
            }

    def search_with_context(self, index_name, s3_url, k=10, scale=10, search_context=None):
        """
        Search for visually similar images with enhanced context from YOLO detection.
        
        This method performs visual search with additional context about the selected item,
        which can help improve search accuracy by focusing on specific clothing items.
        
        params:
            index_name: Name of the search index to use
            s3_url: S3 URL of the image to search for similar images
            k: Number of similar images to return (default: 10)
            scale: Scale factor for the search (default: 10)
            search_context: Dictionary containing context about selected item
                - target_item: The clothing item selected by user
                - confidence: YOLO confidence score for the item
                - bounding_box: Bounding box coordinates [x1, y1, x2, y2]
                - detection_method: Method used for detection (e.g., 'yolo_object_detection')
            
        returns:
            JSON response containing similar image results with enhanced context
        """
        try:
            # Extract S3 key from the full S3 URL
            bucket, key = parse_s3_url(s3_url)
            if not bucket or not key:
                raise ValueError(f"Invalid S3 URL format: {s3_url}")
            
            # Build the search URL with context parameters
            url = f"{self.base_url}/vis-search/search/{index_name}"
            
            # Add query parameters
            params = {
                's3_url': f"s3://{bucket}/{key}",
                'k': k,
                'scale': scale
            }
            
            # Add context parameters if provided
            if search_context:
                if search_context.get('target_item'):
                    params['target_item'] = search_context['target_item']
                if search_context.get('confidence'):
                    params['confidence'] = search_context['confidence']
                if search_context.get('detection_method'):
                    params['detection_method'] = search_context['detection_method']
                if search_context.get('bounding_box'):
                    # Convert bounding box to string format
                    bbox = search_context['bounding_box']
                    if isinstance(bbox, list) and len(bbox) == 4:
                        params['bounding_box'] = ','.join(map(str, bbox))
            
            # Make the request
            response = requests.get(url, params=params, timeout=30)
            
            logger.info(f"Visual Search with Context API call: {url}")
            logger.info(f"Visual Search with Context API params: {params}")
            logger.info(f"Visual Search with Context API response status: {response.status_code}")
            
            response.raise_for_status()
            results = response.json()
            
            # Add context information to results for tracking
            if search_context:
                results['search_context'] = search_context
            
            return results
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Visual Search with Context API connection error: {e}")
            return {
                "error": f"Visual Search with Context API connection error: {str(e)}",
                "status": "connection_error",
                "search_context": search_context
            }
        except Exception as e:
            logger.error(f"Unexpected error in Visual Search with Context: {e}")
            return {
                "error": f"Unexpected error in Visual Search with Context: {str(e)}",
                "status": "error",
                "search_context": search_context
            }


class YOLOService:
    """
    Service class for handling YOLO (You Only Look Once) object detection API calls.
    
    This service provides methods to detect clothing items in images using the team's
    YOLO implementation. It handles API communication with the YOLO detection service.
    
    params:
        base_url: Base URL for the YOLO API
        session: requests.Session instance for making HTTP requests
    """
    
    def __init__(self):
        """Initialize YOLO service with API URL from Django settings."""
        self.base_url = settings.YOLO_API_URL
        self.session = requests.Session()
    
    def test_connection(self):
        """
        Test the connection to the YOLO API using the health endpoint.
        
        returns:
            JSON response from the health endpoint
        """
        try:
            url = f"{self.base_url}/health"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Error testing YOLO API connection: {e}")
            raise
    
    def detect_clothing(self, input_image_s3_url, output_mask_image_dir):
        """
        Detect clothing items in an image using predefined clothing prompts.
        
        This method uses a specific prompt optimized for clothing detection
        and handles the YOLO API interaction for clothing item detection.
        
        params:
            input_image_s3_url: S3 URL of the image to analyze for clothing
            output_mask_image_dir: S3 directory for storing detection mask images
            
        returns:
            JSON response containing clothing detection results or error information
        """
        try:
            logger.info(f"YOLO detection called with S3 URL: {input_image_s3_url}")
            
            #define clothing detection prompt
            prompt = "Jeans,athletic skirt,bar,athletic set,two-piece athletic set, clothes, shirt, dress, top, bottom"
            
            #prepare payload for YOLO API
            payload = {
                "input_image": input_image_s3_url,
                "prompt": prompt,
                "output_mask_image_dir": output_mask_image_dir
            }
            
            #call YOLO API
            url = f"{self.base_url}/predict"
            headers = {"Content-Type": "application/json"}
            
            response = self.session.post(url, json=payload, headers=headers, timeout=120)
            if response.status_code == 200:
                result = response.json()
                logger.info(f"YOLO API response: {json.dumps(result, indent=2)}")
                return result
            else:
                logger.error(f"YOLO API error: {response.status_code} - {response.text}")
                return {
                    "error_message": f"YOLO API returned status {response.status_code}",
                    "status": "failed"
                }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"YOLO API connection error: {e}")
            return {
                "error_message": f"YOLO API connection error: {str(e)}",
                "status": "connection_error"
            }
        except Exception as e:
            logger.error(f"YOLO detection failed: {e}")
            return {
                "error_message": f"YOLO API error: {str(e)}",
                "status": "failed"
            }

    def download_mask_images(self, mask_image_urls):
        """
        Download mask images from S3 and generate public URLs for display.
        
        params:
            mask_image_urls: List of S3 URLs for mask images
            
        returns:
            List of dictionaries with public URLs and metadata for each mask image
        """
        try:
            mask_images = []
            for i, mask_url in enumerate(mask_image_urls):
                try:
                    #generate public URL for the mask image
                    public_url = get_public_url_from_s3_url(mask_url)
                    if public_url:
                        mask_images.append({
                            'index': i,
                            's3_url': mask_url,
                            'public_url': public_url,
                            'filename': mask_url.split('/')[-1]
                        })
                except Exception as e:
                    logger.error(f"Error processing mask image {mask_url}: {e}")
            
            return mask_images
        except Exception as e:
            logger.error(f"Error downloading mask images: {e}")
            return []


class ProductSearchService:
    """
    Main service class that coordinates product search using both DINO and YOLO APIs.
    
    This service orchestrates the entire product search workflow, including:
    1. Uploading images to S3
    2. Running YOLO object detection
    3. Performing DINO visual search
    4. Handling errors gracefully
    
    params:
        visual_search: VisualSearchService instance for DINO operations
        yolo: YOLOService instance for object detection
        s3: S3Service instance for file storage
    """
    
    def __init__(self):
        """Initialize all required services for product search functionality."""
        self.visual_search = VisualSearchService()
        self.yolo = YOLOService()
        self.s3 = S3Service()
    
    def search_product(self, uploaded_image, search_session_id):
        """
        Main method to search for products using both YOLO and DINO APIs.
        
        This method coordinates the entire search workflow:
        1. Uploads the image to S3 using the team lead's pattern (test/ folder)
        2. Runs YOLO detection for clothing items
        3. Attempts DINO visual search 
        4. Returns combined results from both services
        
        params:
            uploaded_image: Django UploadedFile object containing the image
            search_session_id: Unique identifier for this search session
            
        returns:
            Dictionary containing results from both YOLO and DINO services
        """
        try:
            #upload image to S3
            s3_url = self.s3.upload_image(uploaded_image)
            
            #get YOLO detections (simplified)
            output_mask_dir = f"s3://{settings.S3_BUCKET_NAME}/masks/{search_session_id}"
            yolo_results = self.yolo.detect_clothing(s3_url, output_mask_dir)
            
            logger.info(f"YOLO detection results: {json.dumps(yolo_results, indent=2)}")
            
            #try visual search API - use S3 key directly 
            visual_search_results = None
            try:
                index_name = "mall_search_image_250604"
                
                #extract S3 key from URL for direct use
                bucket, key = parse_s3_url(s3_url)
                if bucket and key:

                    url = f"{self.visual_search.base_url}/vis-search/search/{index_name}?s3_url=s3://{bucket}/{key}&k=5&scale=10"
                    
                    response = requests.get(url, timeout=30)
                    response.raise_for_status()
                    visual_search_results = response.json()
                    
                    #add public URLs to search results for image display
                    if isinstance(visual_search_results, dict) and 'result_content' in visual_search_results:
                        for result in visual_search_results['result_content']:
                            if 's3_url' in result:
                                public_url = get_public_url_from_s3_url(result['s3_url'])
                                result['public_url'] = public_url
                    
                    logger.info(f"Visual Search API raw response: {json.dumps(visual_search_results, indent=2)}")
                
            except Exception as e:
                visual_search_results = {
                    "error": "Visual Search API requires authentication. YOLO detection results are still available.",
                    "status": "unauthorized"
                }
                logger.error(f"Visual Search API error: {e}")
                logger.error(f"Visual Search API raw error response: {str(e)}")
            
            return {
                'yolo_results': yolo_results,
                'visual_search_results': visual_search_results,
                's3_url': s3_url,
                'uploaded_image_url': get_public_url_from_s3_url(s3_url)
            }
            
        except Exception as e:
            logger.error(f"Error in product search: {e}")
            raise
    
    def index_product(self, product_code, product_name, s3_url):
        """
        Index a new product in the search system for future visual search.
        
        This method is a placeholder for future product indexing functionality.
        Currently returns a success message as the team's implementation
        doesn't show a create_index method in the search file.
        
        params:
            product_code: Unique identifier for the product
            product_name: Human-readable name of the product
            s3_url: S3 URL of the product image
            
        returns:
            Dictionary containing status and message about indexing operation
        """
        try:
            logger.info(f"Product {product_code} would be indexed with S3 URL: {s3_url}")
            return {"status": "success", "message": "Product indexing not implemented yet"}
        except Exception as e:
            logger.error(f"Error indexing product: {e}")
            raise


def generate_presigned_url(s3_key, expire_seconds=3600):
    """
    Generate a pre-signed URL for an object in an S3 private bucket
    
    Args:
        s3_key: S3 object key, e.g. '250604/images-batch2/C5238/C5238__5067448887.jpg'
        expire_seconds: URL expiration time (seconds), default 1 hour
    
    Returns:
        Pre-signed URL string
    """
    try:
        session = boto3.session.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        s3_client = session.client('s3')
        
        #generate pre-signed url
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.S3_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=expire_seconds
        )
        
        return presigned_url
    except Exception as e:
        logger.error(f"Error generating pre-signed URL: {e}")
        return None


def parse_s3_url(s3_url):
    """
    Parse S3 URL format, extract bucket and key
    
    Args:
        s3_url: S3 URL，例如 's3://mall-picture-search/250604/images-batch2/C5238/C5238__5067448887.jpg'
    
    Returns:
        tuple: (bucket, key)
    """
    if s3_url.startswith('s3://'):
        #remove 's3://' prefix
        path = s3_url[5:]
        #split bucket and key
        parts = path.split('/', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
    return None, None


def get_public_url_from_s3_url(s3_url, expire_seconds=3600):
    """
    Generate a temporary public access link from an S3 URL
    
    Args:
        s3_url: S3 URL, e.g. 's3://mall-picture-search/250604/images-batch2/C5238/C5238__5067448887.jpg'
        expire_seconds: URL expiration time (seconds), default 1 hour
    
    Returns:
        Pre-signed URL string or None if failed
    """
    try:
        bucket, key = parse_s3_url(s3_url)
        
        if bucket and key:
            public_url = generate_presigned_url(key, expire_seconds)
            return public_url
        else:
            logger.error(f"Invalid S3 URL format: {s3_url}")
            return None
    except Exception as e:
        logger.error(f"Error generating public URL for {s3_url}: {e}")
        return None 