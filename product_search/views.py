"""
Product Search Views Module

This module contains Django view functions that handle HTTP requests for the Halara Image Search prototype.
It provides views for product search, image upload, result display, and API endpoints.

The views integrate with the service layer to provide a complete web interface for the image search functionality.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.conf import settings
import uuid
import json
import logging
import requests
from django.utils import timezone

from .models import Product, SearchSession, SearchResult, YOLODetection
from .services import ProductSearchService, VisualSearchService, YOLOService, S3Service, get_public_url_from_s3_url
from .forms import ProductSearchForm, ProductUploadForm

logger = logging.getLogger(__name__)


def index(request):
    """
    Main landing page view that displays the search form.
    
    This view serves as the entry point for users to access the image search functionality.
    
    params:
        request: Django HttpRequest object
        
    returns:
        Rendered template for the main page
    """
    return render(request, 'product_search/index.html')


@require_http_methods(["GET", "POST"])
def search_product(request):
    """
    Handle product search with image upload and YOLO detection.
    
    This view manages the complete search workflow:
    1. Accepts image uploads via POST
    2. Creates search sessions
    3. Calls YOLO API for object detection
    4. Shows detected items for user selection
    5. Performs visual search with selected item
    6. Displays results
    
    params:
        request: Django HttpRequest object containing uploaded image
        
    returns:
        Rendered template with search results or error messages
    """
    if request.method == 'POST':
        # Check if user selected an item or category for visual search
        selected_item_index = request.POST.get('selected_item')
        selected_category = request.POST.get('selected_category')  # 'top' or 'bottom'
        
        if selected_item_index is not None or selected_category is not None:
            # User has selected an item or category, perform visual search
            try:
                selected_item_index = int(selected_item_index) if selected_item_index else None
                
                # Get the session ID from the form
                session_id = request.POST.get('session_id')
                if not session_id:
                    return render(request, 'product_search/search.html', {
                        'error': 'Session not found. Please upload an image again.',
                        'results': None
                    })
                
                # Get the search session and YOLO detection
                search_session = SearchSession.objects.get(session_id=session_id)
                yolo_detection = search_session.yolo_detections.first()
                
                if yolo_detection:
                    yolo_results = yolo_detection.detected_objects
                    if isinstance(yolo_results, dict):
                        phrases = yolo_results.get('phrases', [])
                        scores = yolo_results.get('scores', [])
                        boxes = yolo_results.get('boxes', [])
                    else:
                        phrases = []
                        scores = []
                        boxes = []
                    
                    # Determine which item to search for
                    target_item = None
                    target_confidence = None
                    target_box = None
                    
                    if selected_item_index is not None and selected_item_index < len(phrases):
                        # User selected a specific item
                        target_item = phrases[selected_item_index]
                        target_confidence = scores[selected_item_index]
                        target_box = boxes[selected_item_index] if selected_item_index < len(boxes) else None
                    
                    elif selected_category is not None:
                        # User selected a category (top/bottom), find best matching item
                        top_keywords = ['shirt', 'top', 'blouse', 't-shirt', 'sweater', 'jacket', 'hoodie']
                        bottom_keywords = ['pants', 'jeans', 'skirt', 'shorts', 'leggings', 'trousers', 'bottom']
                        
                        best_match_index = -1
                        best_confidence = 0
                        
                        for i, phrase in enumerate(phrases):
                            phrase_lower = phrase.lower()
                            confidence = scores[i] if i < len(scores) else 0
                            
                            # Check if phrase matches the selected category
                            if selected_category == 'top':
                                if any(keyword in phrase_lower for keyword in top_keywords):
                                    if confidence > best_confidence:
                                        best_match_index = i
                                        best_confidence = confidence
                            elif selected_category == 'bottom':
                                if any(keyword in phrase_lower for keyword in bottom_keywords):
                                    if confidence > best_confidence:
                                        best_match_index = i
                                        best_confidence = confidence
                        
                        if best_match_index >= 0:
                            target_item = phrases[best_match_index]
                            target_confidence = scores[best_match_index]
                            target_box = boxes[best_match_index] if best_match_index < len(boxes) else None
                    
                    if target_item:
                        # Get the cropped mask image URL if available
                        cropped_image_url = None
                        if yolo_detection.output_mask_urls and len(yolo_detection.output_mask_urls) > 0:
                            # Find the corresponding mask image for the selected item
                            if selected_item_index is not None and selected_item_index < len(yolo_detection.output_mask_urls):
                                cropped_image_url = yolo_detection.output_mask_urls[selected_item_index]
                            elif best_match_index >= 0 and best_match_index < len(yolo_detection.output_mask_urls):
                                cropped_image_url = yolo_detection.output_mask_urls[best_match_index]
                        
                        # Use cropped image if available, otherwise use original
                        search_image_url = cropped_image_url if cropped_image_url else search_session.s3_url
                        
                        # Log which image is being used
                        if cropped_image_url:
                            logger.info(f"Using cropped image for visual search: {cropped_image_url}")
                        else:
                            logger.info(f"Using original image for visual search: {search_session.s3_url}")
                        
                        # Perform visual search with selected item
                        visual_search_service = VisualSearchService()
                        search_params = {
                            'index_name': 'mall_search_image_250604',
                            's3_url': search_image_url,  # Use cropped image if available
                            'k': 10,
                            'scale': 10,
                            'search_context': {
                                'target_item': target_item,
                                'confidence': target_confidence,
                                'bounding_box': target_box,
                                'detection_method': 'yolo_object_detection'
                            }
                        }
                        
                        visual_results = visual_search_service.search_with_context(**search_params)
                        
                        # Add public URLs to search results for image display (same as ProductSearchService)
                        if isinstance(visual_results, dict) and 'result_content' in visual_results:
                            for result in visual_results['result_content']:
                                if 's3_url' in result:
                                    public_url = get_public_url_from_s3_url(result['s3_url'])
                                    result['public_url'] = public_url
                        
                        # Save visual search results
                        if visual_results and isinstance(visual_results, list):
                            for result in visual_results:
                                if isinstance(result, dict):
                                    SearchResult.objects.create(
                                        search_session=search_session,
                                        confidence_score=result.get('score', 0.0),
                                        result_type='visual_search_with_context',
                                        metadata={
                                            **result,
                                            'selected_item': target_item,
                                            'yolo_confidence': target_confidence
                                        }
                                    )
                        
                        # Return results with visual search
                        return render(request, 'product_search/search.html', {
                            'results': {
                                'yolo_results': yolo_results,
                                'visual_search_results': visual_results,
                                's3_url': search_session.s3_url,
                                'uploaded_image_url': get_public_url_from_s3_url(search_session.s3_url),
                                'selected_item': target_item,
                                'selected_confidence': target_confidence,
                                'category_selected': selected_category is not None,  # Flag to indicate category selection
                                'used_cropped_image': cropped_image_url is not None  # Flag to show if cropped image was used
                            },
                            'error': None
                        })
            except (ValueError, IndexError, SearchSession.DoesNotExist) as e:
                logger.error(f"Error processing selected item: {e}")
                return render(request, 'product_search/search.html', {
                    'error': f"Error processing selection: {str(e)}",
                    'results': None
                })
        
        # Handle initial image upload
        image_file = request.FILES.get('image')
        if image_file:
            try:
                #create search session
                session_id = str(uuid.uuid4())
                search_session = SearchSession.objects.create(
                    session_id=session_id,
                    uploaded_image=image_file
                )
                
                # Perform initial search using existing ProductSearchService
                search_service = ProductSearchService()
                results = search_service.search_product(
                    image_file, 
                    session_id
                )
                
                # Update search session with S3 URL
                search_session.s3_url = results['s3_url']
                search_session.save()
                
                # Process YOLO results for user choice
                yolo_results = results['yolo_results']
                if isinstance(yolo_results, dict):
                    output_mask_urls = yolo_results.get('mask_image_output', [])
                    phrases = yolo_results.get('phrases', [])
                    scores = yolo_results.get('scores', [])
                    boxes = yolo_results.get('boxes', [])
                else:
                    output_mask_urls = []
                    phrases = []
                    scores = []
                    boxes = []
                
                # Save YOLO detection results
                yolo_detection = YOLODetection.objects.create(
                    search_session=search_session,
                    detected_objects=yolo_results,
                    output_mask_urls=output_mask_urls
                )
                
                # Process mask images for display
                mask_images = []
                if isinstance(yolo_results, dict) and yolo_results.get('mask_image_output'):
                    yolo_service = YOLOService()
                    mask_images = yolo_service.download_mask_images(yolo_results['mask_image_output'])
                
                # Prepare detected items for user choice
                detected_items = []
                if phrases and scores:
                    for i, (phrase, score) in enumerate(zip(phrases, scores)):
                        mask_image = None
                        if i < len(mask_images):
                            mask_image = mask_images[i]
                        
                        detected_items.append({
                            'index': i,
                            'item': phrase,
                            'confidence': score,
                            'confidence_pct': score * 100,
                            'box': boxes[i] if i < len(boxes) else None,
                            'mask_image': mask_image
                        })
                
                # Sort by confidence (highest first)
                detected_items.sort(key=lambda x: x['confidence'], reverse=True)
                
                # Check if we should proceed directly to visual search or show category selection
                if len(detected_items) == 1:
                    # Only one item detected - proceed directly to visual search (original behavior)
                    # Add detected items to results for display
                    results['detected_items'] = detected_items
                    results['session_id'] = session_id  # Add session ID for form submission
                    
                    # Return YOLO detection results for user choice (original behavior)
                    return render(request, 'product_search/search.html', {
                        'results': results,
                        'error': None
                    })
                
                elif len(detected_items) > 1:
                    # Multiple items detected - show category selection
                    results['detected_items'] = detected_items
                    results['multiple_items_detected'] = True
                    results['session_id'] = session_id  # Add session ID for form submission
                    
                    # Return YOLO detection results for user choice
                    return render(request, 'product_search/search.html', {
                        'results': results,
                        'error': None
                    })
                else:
                    # No items detected
                    results['detected_items'] = []
                    results['no_items_detected'] = True
                    results['session_id'] = session_id  # Add session ID for form submission
                    
                    return render(request, 'product_search/search.html', {
                        'results': results,
                        'error': None
                    })
                
            except Exception as e:
                logger.error(f"Error during product search: {e}")
                return render(request, 'product_search/search.html', {
                    'error': f"Error during search: {str(e)}",
                    'results': None
                })
        else:
            return render(request, 'product_search/search.html', {
                'error': 'Please select an image to search.',
                'results': None
            })
    
    #get request - show empty search form
    return render(request, 'product_search/search.html', {
        'error': None,
        'results': None
    })


def search_results(request, session_id):
    """
    Display detailed search results for a specific search session.
    
    This view retrieves and displays all results associated with a search session,
    including YOLO detections and visual search results.
    
    params:
        request: Django HttpRequest object
        session_id: Unique identifier for the search session
        
    returns:
        Rendered template with detailed search results or redirect on error
    """
    try:
        search_session = SearchSession.objects.get(session_id=session_id)
        yolo_detections = search_session.yolo_detections.all()
        search_results = search_session.results.all().order_by('-confidence_score')
        
        context = {
            'search_session': search_session,
            'yolo_detections': yolo_detections,
            'search_results': search_results,
        }
        
        return render(request, 'product_search/results.html', context)
        
    except SearchSession.DoesNotExist:
        messages.error(request, "Search session not found.")
        return redirect('search_product')


@require_http_methods(["GET", "POST"])
def upload_product(request):
    """
    Handle product upload and indexing for the search system.
    
    This view manages the product upload workflow:
    1. Accepts product information and image via form
    2. Creates product record in database
    3. Uploads image to S3
    4. Indexes product for future search
    
    params:
        request: Django HttpRequest object containing product form data
        
    returns:
        Rendered template with upload form or redirect on success
    """
    if request.method == 'POST':
        form = ProductUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create product record
                    product = Product.objects.create(
                        product_code=form.cleaned_data['product_code'],
                        name=form.cleaned_data['name'],
                        description=form.cleaned_data['description'],
                        category=form.cleaned_data['category'],
                        s3_url=''  # Will be updated after S3 upload
                    )
                    
                    # Upload to S3 and index
                    search_service = ProductSearchService()
                    s3_key = f"products/{product.product_code}/{form.cleaned_data['image'].name}"
                    s3_url = search_service.s3.upload_fileobj(
                        form.cleaned_data['image'], 
                        s3_key
                    )
                    
                    # Update product with S3 URL
                    product.s3_url = s3_url
                    product.save()
                    
                    # Index the product
                    search_service.index_product(
                        product.product_code,
                        product.name,
                        s3_url
                    )
                    
                    messages.success(request, f"Product '{product.name}' uploaded and indexed successfully!")
                    return redirect('product_list')
                    
            except Exception as e:
                logger.error(f"Error uploading product: {e}")
                messages.error(request, f"Error uploading product: {str(e)}")
                return render(request, 'product_search/upload_product.html', {'form': form})
    else:
        form = ProductUploadForm()
    
    return render(request, 'product_search/upload_product.html', {'form': form})


def product_list(request):
    """
    Display paginated list of all products in the system.
    
    This view provides a browseable interface for viewing all products
    that have been uploaded and indexed.
    
    params:
        request: Django HttpRequest object
        
    returns:
        Rendered template with paginated product list
    """
    products = Product.objects.all().order_by('-created_at')
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'product_search/product_list.html', {'page_obj': page_obj})


def product_detail(request, product_id):
    """
    Display detailed information for a specific product.
    
    This view shows comprehensive information about a single product,
    including its metadata and associated image.
    
    params:
        request: Django HttpRequest object
        product_id: Primary key of the product to display
        
    returns:
        Rendered template with product details or redirect on error
    """
    try:
        product = Product.objects.get(id=product_id)
        return render(request, 'product_search/product_detail.html', {'product': product})
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
        return redirect('product_list')


@require_http_methods(["POST"])
@csrf_exempt
def api_search(request):
    """
    API endpoint for programmatic product search.
    
    This endpoint provides a JSON API for performing product searches
    programmatically. It accepts image data and returns structured results.
    
    params:
        request: Django HttpRequest object containing image data
        
    returns:
        JSON response with search results or error information
    """
    try:
        image_file = request.FILES.get('image')
        if not image_file:
            return JsonResponse({
                'error': 'No image provided',
                'status': 'error'
            }, status=400)
        
        #create search session
        session_id = str(uuid.uuid4())
        search_session = SearchSession.objects.create(
            session_id=session_id,
            uploaded_image=image_file
        )
        
        #perform search
        search_service = ProductSearchService()
        results = search_service.search_product(image_file, session_id)
        
        #save results to database
        yolo_results = results['yolo_results']
        if isinstance(yolo_results, dict):
            output_mask_urls = yolo_results.get('mask_image_output', [])
        else:
            output_mask_urls = []
        
        yolo_detection = YOLODetection.objects.create(
            search_session=search_session,
            detected_objects=yolo_results,
            output_mask_urls=output_mask_urls
        )
        
        #save visual search results
        if 'visual_search_results' in results and results['visual_search_results']:
            visual_results = results['visual_search_results']
            if isinstance(visual_results, list):
                for result in visual_results:
                    if isinstance(result, dict):
                        SearchResult.objects.create(
                            search_session=search_session,
                            confidence_score=result.get('score', 0.0),
                            result_type='visual_search',
                            metadata=result
                        )
        
        #update session with s3 url
        search_session.s3_url = results['s3_url']
        search_session.save()
        
        return JsonResponse({
            'session_id': session_id,
            'results': results,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"API search error: {e}")
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        }, status=500)


def api_test_connection(request):
    """
    API endpoint for testing external service connections.
    
    This endpoint tests connectivity to both YOLO and Visual Search APIs
    to verify that the external services are accessible.
    
    params:
        request: Django HttpRequest object
        
    returns:
        JSON response with connection test results
    """
    try:
        results = {}
        
        #test yolo api
        try:
            yolo_service = YOLOService()
            yolo_response = yolo_service.test_connection()
            results['yolo'] = {
                'status': 'connected',
                'response': yolo_response
            }
        except Exception as e:
            results['yolo'] = {
                'status': 'error',
                'error': str(e)
            }
        
        #test visual search api
        try:
            visual_service = VisualSearchService()
            test_s3_url = "s3://a-bucket/image.png"
            visual_response = visual_service.test_connection(test_s3_url)
            results['visual_search'] = {
                'status': 'connected',
                'response': visual_response
            }
        except Exception as e:
            #try listing indexes as an alternative test
            try:
                visual_service = VisualSearchService()
                indexes_response = visual_service.list_indexes()
                results['visual_search'] = {
                    'status': 'connected (via list_indexes)',
                    'response': indexes_response
                }
            except Exception as e2:
                results['visual_search'] = {
                    'status': 'error',
                    'error': f"Test connection failed: {str(e)}. List indexes also failed: {str(e2)}"
                }
        
        return JsonResponse({
            'status': 'success',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"API test connection error: {e}")
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        }, status=500)


def api_test_yolo(request):
    """
    API endpoint for testing YOLO API functionality.
    
    This endpoint performs a test call to the YOLO API to verify
    that it can process requests and return results.
    
    params:
        request: Django HttpRequest object
        
    returns:
        JSON response with YOLO API test results
    """
    try:
        yolo_service = YOLOService()
        
        #test with a simple s3 url to see what the api expects
        test_s3_url = f"s3://{settings.S3_BUCKET_NAME}/test/test.jpg"
        test_output_dir = f"s3://{settings.S3_BUCKET_NAME}/test/masks"
        
        logger.info(f"Testing YOLO API with S3 URL: {test_s3_url}")
        
        try:
            result = yolo_service.detect_clothing(test_s3_url, test_output_dir)
            return JsonResponse({
                'status': 'success',
                'result': result,
                'test_s3_url': test_s3_url,
                'test_output_dir': test_output_dir
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'error': str(e),
                'test_s3_url': test_s3_url,
                'test_output_dir': test_output_dir
            })
            
    except Exception as e:
        logger.error(f"API test YOLO error: {e}")
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        }, status=500)


def health_check(request):
    """
    Health check endpoint for monitoring and deployment verification.
    
    This endpoint provides a simple health check that can be used by
    load balancers, monitoring systems, and deployment pipelines.
    
    params:
        request: Django HttpRequest object
        
    returns:
        JSON response indicating service health status
    """
    try:
        #basic health check - can be extended with database checks, etc.
        return JsonResponse({
            'status': 'healthy',
            'service': 'halara_image_search',
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)


def api_test_yolo_simple(request):
    """
    Simple YOLO test endpoint that mimics the team lead's script exactly.
    
    This endpoint tests the YOLO API using the same approach as the team lead's
    working script to isolate any issues.
    
    params:
        request: Django HttpRequest object
        
    returns:
        JSON response with YOLO API test results
    """
    try:
        yolo_service = YOLOService()
        
        #test 1: health check (like team lead's test_yolo_network)
        try:
            health_response = yolo_service.test_connection()
            health_result = {
                'health_check': 'success',
                'response': health_response,
                'yolo_endpoint': yolo_service.base_url
            }
        except Exception as e:
            health_result = {
                'health_check': 'failed',
                'error': str(e),
                'yolo_endpoint': yolo_service.base_url
            }
        
        #test 2: simple predict with test s3 url (like team lead's approach)
        try:
            test_s3_url = "s3://mall-picture-search/test/test.jpg"
            test_prompt = "test"
            test_output_dir = "s3://mall-picture-search/test/masks"
            
            predict_result = yolo_service.predict(test_s3_url, test_prompt, test_output_dir)
            predict_response = {
                'predict_test': 'success',
                'response': predict_result
            }
        except Exception as e:
            predict_response = {
                'predict_test': 'failed',
                'error': str(e)
            }
        
        return JsonResponse({
            'status': 'success',
            'yolo_tests': {
                'health': health_result,
                'predict': predict_response
            }
        })
        
    except Exception as e:
        logger.error(f"Simple YOLO test error: {e}")
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        }, status=500)
