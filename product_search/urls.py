"""
Product Search URL Configuration

This module defines the URL patterns for the Halara Image Search prototype.
It includes routes for web pages, API endpoints, and product management functionality.

The URL patterns are organized by functionality and provide clean, RESTful endpoints
for the applications features.
"""

from django.urls import path
from . import views

app_name = 'product_search'

urlpatterns = [
    # Health check endpoint for monitoring
    path('health/', views.health_check, name='health_check'),
    
    # Main application pages
    path('', views.index, name='index'),
    path('search/', views.search_product, name='search_product'),
    path('results/<str:session_id>/', views.search_results, name='search_results'),
    
    # Product management pages
    path('upload/', views.upload_product, name='upload_product'),
    path('products/', views.product_list, name='product_list'),
    path('products/<uuid:product_id>/', views.product_detail, name='product_detail'),
    
    # API endpoints for programmatic access
    path('api/search/', views.api_search, name='api_search'),
    path('api/test-connection/', views.api_test_connection, name='api_test_connection'),
    path('api/test-yolo/', views.api_test_yolo, name='api_test_yolo'),
    path('api/test-yolo-simple/', views.api_test_yolo_simple, name='api_test_yolo_simple'),
] 