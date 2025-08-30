"""
Production Settings for Halara Image Search

This module contains production-specific Django settings for the Halara Image Search prototype.
It includes security configurations, performance optimizations, and production-ready settings.

Import this file in production by setting DJANGO_SETTINGS_MODULE=halara_search.production
"""

from .settings import *
import os

#security settings
DEBUG = False
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-production-key-change-this')
#allow all hosts in production (safe behind load balancer)
ALLOWED_HOSTS = ['*']

#https settings (only if https is available)
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'False').lower() == 'true'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

#database configuration (postgresql for production, fallback to sqlite)
DB_ENGINE = os.environ.get('DB_ENGINE', 'sqlite')
if DB_ENGINE == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'halara_search'),
            'USER': os.environ.get('DB_USER', 'halara_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'OPTIONS': {
                'sslmode': 'require',
            },
        }
    }
else:
    #fallback to sqlite for development/testing
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

#static files configuration
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

#media files configuration
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

#logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'product_search': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

#cache configuration (redis for production, fallback to local memory)
REDIS_URL = os.environ.get('REDIS_URL')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    #fallback to database sessions
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

#aws configuration (from environment variables)
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', '')

#api configuration
VISUAL_SEARCH_API_URL = os.environ.get('VISUAL_SEARCH_API_URL', 'https://90k8td91vk.execute-api.us-west-2.amazonaws.com/api')
# Use direct IP for GitLab deployment (outside AWS VPC)
YOLO_API_URL = os.environ.get('YOLO_API_URL', 'http://44.249.60.118:5000')

#security headers (only if behind proxy)
if os.environ.get('BEHIND_PROXY', 'False').lower() == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

#file upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  #10mb
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  #10mb

#performance settings
CONN_MAX_AGE = 60 