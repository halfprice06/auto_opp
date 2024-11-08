// static/app.js

// Handle file upload and display
const fileInput = document.getElementById('file-upload');
const fileNameDisplay = document.getElementById('file-name');
const pdfViewer = document.getElementById('pdf-viewer');
const conversationId = document.getElementById('conversation-id');
const textarea = document.querySelector('textarea');
const form = document.querySelector('.chat-input-form');

fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (file) {
        console.log('File selected:', file.name);
        fileNameDisplay.textContent = file.name;
        const fileURL = URL.createObjectURL(file);
        pdfViewer.src = fileURL;
        
        // Clear conversation ID when new file is uploaded
        conversationId.value = '';
    }
});

// Form validation and submission
form.addEventListener('htmx:beforeRequest', function(evt) {
    console.log('=== HTMX Request Starting ===');
    const instruction = textarea.value.trim();
    const hasConversationId = conversationId.value !== '';
    
    console.log('Current state:', {
        instruction,
        conversationId: conversationId.value,
        hasFile: fileInput.files.length > 0
    });
    
    if (!instruction) {
        console.log('No instruction provided - preventing request');
        evt.preventDefault();
        return;
    }
    
    if (fileInput.files.length === 0 && !hasConversationId) {
        console.log('No file or conversation ID - preventing request');
        evt.preventDefault();
        alert('Please upload a PDF file first');
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('instruction', instruction);
        
        // Always append conversation_id if it exists
        if (conversationId.value) {
            console.log('Adding conversation_id:', conversationId.value);
            formData.append('conversation_id', conversationId.value);
        }
        
        // Only append file for new conversations
        if (!hasConversationId) {
            const file = fileInput.files[0];
            if (file) {
                console.log('Adding file:', file.name);
                formData.append('file', file, file.name);
            }
        }
        
        evt.detail.formData = formData;
        evt.detail.isFormData = true;
        
        // Log what we're sending
        console.log('Sending FormData:');
        for (let pair of formData.entries()) {
            console.log(`${pair[0]}: ${pair[1] instanceof File ? pair[1].name : pair[1]}`);
        }
    } catch (error) {
        console.error('Error preparing form data:', error);
        evt.preventDefault();
    }
});

// Clear textarea after successful request
form.addEventListener('htmx:afterRequest', function(evt) {
    if (evt.detail.successful) {
        textarea.value = '';
        textarea.style.height = 'auto';
        
        // Scroll to bottom
        const messagesContainer = document.querySelector('.chat-messages');
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
});

// Add more detailed logging for the actual request
document.body.addEventListener('htmx:beforeSend', function(evt) {
    console.log('=== HTMX Sending Request ===');
    console.log('Request Details:', {
        method: evt.detail.xhr.method,
        url: evt.detail.xhr.url,
        headers: evt.detail.headers,
        parameters: evt.detail.parameters,
        target: evt.detail.target
    });
    
    // Log FormData if available
    if (evt.detail.formData) {
        console.log('Request FormData contents:');
        for (let pair of evt.detail.formData.entries()) {
            console.log(`${pair[0]}: ${pair[1] instanceof File ? pair[1].name : pair[1]}`);
        }
    }
});

// Auto-resize textarea
textarea.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

// More detailed error handling
document.body.addEventListener('htmx:responseError', function(evt) {
    console.error('=== HTMX Error Details ===');
    console.error('Status:', evt.detail.xhr.status);
    console.error('Status Text:', evt.detail.xhr.statusText);
    console.error('Response:', evt.detail.xhr.response);
    console.error('Headers:', evt.detail.xhr.getAllResponseHeaders());
    
    const messagesContainer = document.querySelector('.chat-messages');
    const errorMessage = document.createElement('div');
    errorMessage.className = 'message error-message';
    
    // Try to get more detailed error message
    let errorText = 'An error occurred. Please try again.';
    try {
        const response = JSON.parse(evt.detail.xhr.response);
        if (response.detail) {
            errorText = response.detail;
        }
        console.error('Parsed error response:', response);
    } catch (e) {
        console.error('Could not parse error response:', e);
        console.error('Raw response:', evt.detail.xhr.response);
    }
    
    errorMessage.textContent = errorText;
    messagesContainer.appendChild(errorMessage);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}); 