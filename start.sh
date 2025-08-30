#!/bin/bash

#startup script for halara image search django application

set -e

echo "Starting Halara Image Search application..."

#set django settings - use production by default, but allow override
if [ -z "$DJANGO_SETTINGS_MODULE" ]; then
    #check if we're in production (has production-like environment variables)
    if [ -n "$DFS_SVC_NAME" ] || [ -n "$KUBERNETES_SERVICE_HOST" ]; then
        export DJANGO_SETTINGS_MODULE=halara_search.production
        echo "Production environment detected, using production settings"
    else
        export DJANGO_SETTINGS_MODULE=halara_search.settings
        echo "Development environment detected, using development settings"
    fi
fi

echo "Using Django settings: $DJANGO_SETTINGS_MODULE"

#wait for database to be ready (if using external database)
if [ -n "$DB_HOST" ]; then
    echo "Waiting for database to be ready at $DB_HOST:${DB_PORT:-5432}..."
    timeout=30
    counter=0
    while ! nc -z $DB_HOST ${DB_PORT:-5432} && [ $counter -lt $timeout ]; do
        echo "Database not ready, waiting... ($counter/$timeout)"
        sleep 1
        counter=$((counter + 1))
    done
    
    if [ $counter -eq $timeout ]; then
        echo "Warning: Database connection timeout, proceeding anyway..."
    else
        echo "Database is ready!"
    fi
fi

#run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput || {
    echo "Warning: Database migration failed, but continuing..."
}

#collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput || {
    echo "Warning: Static file collection failed, but continuing..."
}

#create superuser if environment variables are set
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Creating superuser..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
" || echo "Warning: Superuser creation failed, but continuing..."
fi

#start the application
echo "Starting Django application on 0.0.0.0:8000..."
exec python manage.py runserver 0.0.0.0:8000 