// Facebook Video Downloader - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const downloadForm = document.getElementById('downloadForm');
    const downloadBtn = document.getElementById('downloadBtn');
    const urlInput = document.getElementById('url');
    
    // URL validation
    function validateFacebookUrl(url) {
        const facebookDomains = [
            'facebook.com',
            'www.facebook.com',
            'm.facebook.com',
            'fb.watch'
        ];
        
        try {
            const urlObj = new URL(url);
            return facebookDomains.some(domain => 
                urlObj.hostname.toLowerCase().includes(domain)
            );
        } catch {
            return false;
        }
    }
    
    // Real-time URL validation
    if (urlInput) {
        urlInput.addEventListener('input', function() {
            const url = this.value.trim();
            const isValid = url === '' || validateFacebookUrl(url);
            
            if (url && !isValid) {
                this.classList.add('is-invalid');
            } else {
                this.classList.remove('is-invalid');
            }
        });
    }
    
    // Form submission handling
    if (downloadForm) {
        downloadForm.addEventListener('submit', function(e) {
            const url = urlInput.value.trim();
            
            if (!url) {
                e.preventDefault();
                showAlert('Please enter a Facebook video URL', 'danger');
                return;
            }
            
            if (!validateFacebookUrl(url)) {
                e.preventDefault();
                showAlert('Please enter a valid Facebook video URL', 'danger');
                return;
            }
            
            // Show loading state
            downloadBtn.disabled = true;
            downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Starting Download...';
            
            // Re-enable button after a delay (in case of errors)
            setTimeout(() => {
                downloadBtn.disabled = false;
                downloadBtn.innerHTML = '<i class="fas fa-download me-2"></i>Start Download';
            }, 5000);
        });
    }
    
    // Utility function to show alerts
    function showAlert(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.container');
        const firstChild = container.firstElementChild;
        container.insertBefore(alertDiv, firstChild);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alertDiv && alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
    
    // Format file size
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    // Format duration
    function formatDuration(seconds) {
        if (!seconds) return 'Unknown';
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
    
    // Copy download ID functionality
    document.addEventListener('click', function(e) {
        if (e.target && e.target.id === 'downloadId') {
            const downloadId = e.target.textContent;
            navigator.clipboard.writeText(downloadId).then(() => {
                showAlert('Download ID copied to clipboard!', 'success');
            }).catch(() => {
                showAlert('Failed to copy download ID', 'warning');
            });
        }
    });
    
    // Auto-refresh functionality for progress tracking
    let autoRefreshInterval;
    
    function startAutoRefresh() {
        if (document.getElementById('progressSection')) {
            autoRefreshInterval = setInterval(() => {
                const statusBadge = document.getElementById('downloadStatus');
                if (statusBadge && (statusBadge.textContent === 'Completed' || statusBadge.textContent === 'Error')) {
                    clearInterval(autoRefreshInterval);
                }
            }, 2000);
        }
    }
    
    // Cleanup function
    window.addEventListener('beforeunload', function() {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
        }
    });
    
    // Initialize auto-refresh if needed
    startAutoRefresh();
});

// Global functions for dynamic content
window.FacebookDownloader = {
    formatFileSize: function(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    formatDuration: function(seconds) {
        if (!seconds) return 'Unknown';
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
};
