"""
Product Search Forms Module

This module contains Django forms for handling user input in the Halara Image Search prototype.
It includes forms for product search, product upload, and bulk operations.

The forms provide validation, user-friendly widgets, and integration with the models
to ensure data integrity and user experience.
"""

from django import forms
from .models import Product


class ProductSearchForm(forms.Form):
    """
    Form for product search with image upload and validation.
    
    This form handles image uploads for product search functionality.
    It includes validation for file size, file type, and provides
    user-friendly widgets for image selection.
    
    params:
        image: ImageField for uploading product images with validation
    """
    
    image = forms.ImageField(
        label='Upload Product Image',
        help_text='Upload an image of the product you want to search for',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'id': 'image-upload'
        })
    )
    
    def clean_image(self):
        """
        Validate uploaded image file for size and type.
        
        This method ensures that uploaded images meet the system requirements
        for file size and format before processing.
        
        returns:
            Validated image file or raises ValidationError
            
        raises:
            ValidationError: If file size exceeds 10MB or file type is not supported
        """
        image = self.cleaned_data.get('image')
        if image:
            # Check file size (max 10MB)
            if image.size > 10 * 1024 * 1024:
                raise forms.ValidationError("Image file size must be less than 10MB.")
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if image.content_type not in allowed_types:
                raise forms.ValidationError("Please upload a valid image file (JPEG, PNG, GIF).")
        
        return image


class ProductUploadForm(forms.ModelForm):
    """
    Form for uploading and indexing new products in the search system.
    
    This form handles the complete product upload workflow, including
    product metadata and image upload. It provides validation for
    product codes, image files, and integrates with the Product model.
    
    params:
        image: ImageField for uploading product images
        product_code: TextInput for unique product identifier
        name: TextInput for product name
        description: Textarea for product description
        category: TextInput for product category
    """
    
    image = forms.ImageField(
        label='Product Image',
        help_text='Upload a high-quality image of the product',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )
    
    class Meta:
        """Meta configuration for the ProductUploadForm."""
        model = Product
        fields = ['product_code', 'name', 'description', 'category']
        widgets = {
            'product_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., HAL001, SKU123'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Product name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Product description'
            }),
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Athletic Wear, Jeans, Dresses'
            }),
        }
    
    def clean_product_code(self):
        """
        Validate product code for uniqueness.
        
        This method ensures that each product code is unique in the system
        to prevent conflicts and maintain data integrity.
        
        returns:
            Validated product code or raises ValidationError
            
        raises:
            ValidationError: If product code already exists in the database
        """
        product_code = self.cleaned_data.get('product_code')
        if product_code:
            # Check if product code already exists
            if Product.objects.filter(product_code=product_code).exists():
                raise forms.ValidationError("A product with this code already exists.")
        return product_code
    
    def clean_image(self):
        """
        Validate uploaded image file for size and type.
        
        This method ensures that uploaded product images meet the system requirements
        for file size and format before processing and indexing.
        
        returns:
            Validated image file or raises ValidationError
            
        raises:
            ValidationError: If file size exceeds 10MB or file type is not supported
        """
        image = self.cleaned_data.get('image')
        if image:
            # Check file size (max 10MB)
            if image.size > 10 * 1024 * 1024:
                raise forms.ValidationError("Image file size must be less than 10MB.")
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if image.content_type not in allowed_types:
                raise forms.ValidationError("Please upload a valid image file (JPEG, PNG, GIF).")
        
        return image


class BulkUploadForm(forms.Form):
    """
    Form for bulk product upload using CSV files.
    
    This form handles bulk product uploads via CSV files containing
    product information. It provides validation for CSV file format
    and size to ensure data quality.
    
    params:
        csv_file: FileField for uploading CSV files with product data
    """
    
    csv_file = forms.FileField(
        label='CSV File',
        help_text='Upload a CSV file with product information (product_code, name, description, category, image_url)',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        })
    )
    
    def clean_csv_file(self):
        """
        Validate uploaded CSV file for size and format.
        
        This method ensures that uploaded CSV files meet the system requirements
        for file size and format before processing bulk uploads.
        
        returns:
            Validated CSV file or raises ValidationError
            
        raises:
            ValidationError: If file size exceeds 5MB or file is not a valid CSV
        """
        csv_file = self.cleaned_data.get('csv_file')
        if csv_file:
            # Check file size (max 5MB)
            if csv_file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("CSV file size must be less than 5MB.")
            
            # Check file type
            if not csv_file.name.endswith('.csv'):
                raise forms.ValidationError("Please upload a valid CSV file.")
        
        return csv_file 