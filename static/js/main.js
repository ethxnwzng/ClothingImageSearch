// Main JavaScript file for Halara Product Search

// Utility function to show loading state
function showLoading(element, text = 'Loading...') {
    const originalContent = element.innerHTML;
    element.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${text}`;
    element.disabled = true;
    return originalContent;
}

// Utility function to restore element state
function restoreElement(element, originalContent) {
    element.innerHTML = originalContent;
    element.disabled = false;
}

// Utility function to show success message
function showSuccess(message, duration = 3000) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-success alert-dismissible fade show';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Insert at the top of the main container
    const mainContainer = document.querySelector('main .container');
    if (mainContainer) {
        mainContainer.insertBefore(alertDiv, mainContainer.firstChild);
        
        // Auto-remove after duration
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, duration);
    }
}

// Utility function to show error message
function showError(message, duration = 5000) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-danger alert-dismissible fade show';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Insert at the top of the main container
    const mainContainer = document.querySelector('main .container');
    if (mainContainer) {
        mainContainer.insertBefore(alertDiv, mainContainer.firstChild);
        
        // Auto-remove after duration
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, duration);
    }
}

// Image preview functionality
function setupImagePreview(inputId, previewId) {
    const input = document.getElementById(inputId);
    const preview = document.getElementById(previewId);
    
    if (input && preview) {
        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        });
    }
}

// Form validation enhancement
function enhanceFormValidation() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                const originalContent = showLoading(submitBtn, 'Processing...');
                
                // Store the original content to restore later
                submitBtn.dataset.originalContent = originalContent;
            }
        });
    });
}

// Initialize common functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Enhance form validation
    enhanceFormValidation();
    
    // Setup image previews if they exist
    setupImagePreview('image-upload', 'image-preview');
    
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert.parentNode) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    });
    
    // Add smooth scrolling to anchor links
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
});

// Export utility functions for use in other scripts
window.HalaraUtils = {
    showLoading,
    restoreElement,
    showSuccess,
    showError,
    setupImagePreview
}; 