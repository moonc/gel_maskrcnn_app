// Global JavaScript for Gel Spot Detection App

// Socket.IO connection
const socket = io();

// Utility functions
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

// Socket.IO event handlers
socket.on('connect', function() {
    console.log('Connected to server');
});

socket.on('disconnect', function() {
    console.log('Disconnected from server');
});

socket.on('job_progress', function(data) {
    updateJobProgress(data);
});

function updateJobProgress(data) {
    const progressBar = document.getElementById('progressBar');
    const statusBadge = document.getElementById('statusBadge');
    const progressText = document.getElementById('progressText');
    
    if (progressBar) {
        progressBar.style.width = data.progress + '%';
        progressBar.setAttribute('aria-valuenow', data.progress);
    }
    
    if (statusBadge) {
        let badgeClass = 'bg-primary';
        let icon = 'fa-spinner fa-spin';
        
        switch(data.status) {
            case 'completed':
                badgeClass = 'bg-success';
                icon = 'fa-check';
                break;
            case 'failed':
                badgeClass = 'bg-danger';
                icon = 'fa-times';
                break;
            case 'cancelled':
                badgeClass = 'bg-warning';
                icon = 'fa-stop';
                break;
        }
        
        statusBadge.className = `badge fs-6 ${badgeClass}`;
        statusBadge.innerHTML = `<i class="fas ${icon} me-1"></i>${data.status.charAt(0).toUpperCase() + data.status.slice(1)}`;
    }
    
    if (progressText) {
        progressText.textContent = `${data.progress}% complete`;
    }
    
    // Redirect to results if completed
    if (data.status === 'completed') {
        setTimeout(() => {
            window.location.href = `/results/${data.job_id}`;
        }, 2000);
    }
}

// File upload validation
function validateFile(file) {
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/bmp', 'image/tiff'];
    const maxSize = 16 * 1024 * 1024; // 16MB
    
    if (!allowedTypes.includes(file.type)) {
        showAlert('Please select a valid image file (PNG, JPG, JPEG, BMP, TIFF)', 'danger');
        return false;
    }
    
    if (file.size > maxSize) {
        showAlert('File size must be less than 16MB', 'danger');
        return false;
    }
    
    return true;
}

// Initialize tooltips and popovers
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize Bootstrap popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});