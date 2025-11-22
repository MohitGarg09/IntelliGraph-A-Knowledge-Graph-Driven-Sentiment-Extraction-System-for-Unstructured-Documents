// Configuration
const API_BASE_URL = 'http://localhost:8000';

// Global state
let currentTab = 'upload';
let candidates = [];
let systemHealth = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

async function initializeApp() {
    setupEventListeners();
    await checkSystemHealth();
    await loadCandidates();
    await loadProcessingStatus();
}

// Event Listeners Setup
function setupEventListeners() {
    // Tab navigation
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Upload functionality
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');

    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
    fileInput.addEventListener('change', handleFileSelect);

    // Query functionality
    document.getElementById('querySubmit').addEventListener('click', submitQuery);
    document.getElementById('queryInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
            submitQuery();
        }
    });

    // ATS Analysis functionality
    document.getElementById('analyzeAll').addEventListener('click', analyzeAllResumes);
    document.getElementById('analyzeSingle').addEventListener('click', toggleSingleResumeInput);
    document.getElementById('submitSingleATS').addEventListener('click', analyzeSingleResume);

    // Candidate search
    document.getElementById('candidateSearch').addEventListener('input', filterCandidates);

    // Modal close
    document.getElementById('candidateModal').addEventListener('click', (e) => {
        if (e.target.id === 'candidateModal') {
            closeCandidateModal();
        }
    });
}

// Tab Management
function switchTab(tabName) {
    // Update nav tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tabName).classList.add('active');

    currentTab = tabName;

    // Load data for specific tabs
    if (tabName === 'candidates') {
        loadCandidates();
    } else if (tabName === 'status') {
        loadProcessingStatus();
        checkSystemHealth();
    }
}

// System Health Check
async function checkSystemHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        systemHealth = await response.json();
        
        updateHealthIndicator();
        updateStatusCards();
    } catch (error) {
        console.error('Health check failed:', error);
        systemHealth = {
            status: 'unhealthy',
            neo4j_connected: false,
            rag_system_ready: false,
            api_key_configured: false
        };
        updateHealthIndicator();
    }
}

function updateHealthIndicator() {
    const indicator = document.getElementById('statusIndicator');
    const statusText = document.getElementById('statusText');
    
    if (!systemHealth) {
        indicator.className = 'status-indicator checking';
        statusText.textContent = 'Checking...';
        return;
    }

    if (systemHealth.status === 'healthy') {
        indicator.className = 'status-indicator healthy';
        statusText.textContent = 'System Healthy';
    } else {
        indicator.className = 'status-indicator unhealthy';
        statusText.textContent = 'System Issues';
    }
}

function updateStatusCards() {
    if (!systemHealth) return;

    const dbStatus = document.getElementById('dbStatus');
    const ragStatus = document.getElementById('ragStatus');
    const apiStatus = document.getElementById('apiStatus');

    dbStatus.innerHTML = systemHealth.neo4j_connected 
        ? '<span class="status-healthy"><i class="fas fa-check-circle"></i> Connected</span>'
        : '<span class="status-unhealthy"><i class="fas fa-times-circle"></i> Disconnected</span>';

    ragStatus.innerHTML = systemHealth.rag_system_ready
        ? '<span class="status-healthy"><i class="fas fa-check-circle"></i> Ready</span>'
        : '<span class="status-unhealthy"><i class="fas fa-times-circle"></i> Not Ready</span>';

    apiStatus.innerHTML = systemHealth.api_key_configured
        ? '<span class="status-healthy"><i class="fas fa-check-circle"></i> Configured</span>'
        : '<span class="status-unhealthy"><i class="fas fa-times-circle"></i> Not Configured</span>';
}

// File Upload Handling
function handleDragOver(e) {
    e.preventDefault();
    document.getElementById('uploadArea').classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    document.getElementById('uploadArea').classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    document.getElementById('uploadArea').classList.remove('dragover');
    
    const files = Array.from(e.dataTransfer.files).filter(file => 
        file.type === 'application/pdf'
    );
    
    if (files.length === 0) {
        showToast('Please select PDF files only', 'warning');
        return;
    }
    
    uploadFiles(files);
}

function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    uploadFiles(files);
}

async function uploadFiles(files) {
    const uploadProgress = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const uploadedFiles = document.getElementById('uploadedFiles');

    uploadProgress.style.display = 'block';
    uploadedFiles.innerHTML = '';

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const progress = ((i + 1) / files.length) * 100;
        
        progressFill.style.width = `${progress}%`;
        progressText.textContent = `Uploading ${file.name} (${i + 1}/${files.length})`;

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(`${API_BASE_URL}/upload-resume`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            
            const fileItem = createFileItem(file.name, 'processing');
            uploadedFiles.appendChild(fileItem);

            if (response.ok) {
                showToast(`${file.name} uploaded successfully`, 'success');
                // Poll for processing completion
                pollProcessingStatus(file.name, fileItem);
            } else {
                updateFileStatus(fileItem, 'error', result.detail || 'Upload failed');
                showToast(`Failed to upload ${file.name}`, 'error');
            }
        } catch (error) {
            console.error('Upload error:', error);
            const fileItem = createFileItem(file.name, 'error');
            uploadedFiles.appendChild(fileItem);
            showToast(`Error uploading ${file.name}`, 'error');
        }
    }

    uploadProgress.style.display = 'none';
    
    // Refresh candidates list after upload
    setTimeout(() => {
        loadCandidates();
    }, 2000);
}

function createFileItem(filename, status) {
    const fileItem = document.createElement('div');
    fileItem.className = 'file-item';
    fileItem.innerHTML = `
        <div class="file-info">
            <i class="fas fa-file-pdf"></i>
            <span>${filename}</span>
        </div>
        <div class="file-status ${status}">
            <i class="fas ${getStatusIcon(status)}"></i>
            <span>${getStatusText(status)}</span>
        </div>
    `;
    return fileItem;
}

function updateFileStatus(fileItem, status, message = null) {
    const statusDiv = fileItem.querySelector('.file-status');
    statusDiv.className = `file-status ${status}`;
    statusDiv.innerHTML = `
        <i class="fas ${getStatusIcon(status)}"></i>
        <span>${message || getStatusText(status)}</span>
    `;
}

function getStatusIcon(status) {
    const icons = {
        processing: 'fa-spinner fa-spin',
        success: 'fa-check-circle',
        error: 'fa-times-circle'
    };
    return icons[status] || 'fa-question-circle';
}

function getStatusText(status) {
    const texts = {
        processing: 'Processing...',
        success: 'Processed',
        error: 'Failed'
    };
    return texts[status] || 'Unknown';
}

async function pollProcessingStatus(filename, fileItem) {
    // Simple polling mechanism - in production, consider WebSockets
    let attempts = 0;
    const maxAttempts = 30; // 5 minutes max
    
    const poll = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/processing-status`);
            const status = await response.json();
            
            const processedFile = status.details.find(detail => 
                detail.filename === filename && detail.status === 'processed'
            );
            
            const failedFile = status.details.find(detail => 
                detail.filename === filename && detail.status === 'failed'
            );

            if (processedFile) {
                updateFileStatus(fileItem, 'success');
                return;
            } else if (failedFile) {
                updateFileStatus(fileItem, 'error', failedFile.error || 'Processing failed');
                return;
            }

            attempts++;
            if (attempts < maxAttempts) {
                setTimeout(poll, 10000); // Check every 10 seconds
            } else {
                updateFileStatus(fileItem, 'error', 'Processing timeout');
            }
        } catch (error) {
            console.error('Polling error:', error);
            updateFileStatus(fileItem, 'error', 'Status check failed');
        }
    };

    setTimeout(poll, 5000); // Start polling after 5 seconds
}

// Candidates Management
async function loadCandidates() {
    const candidatesGrid = document.getElementById('candidatesGrid');
    
    try {
        candidatesGrid.innerHTML = `
            <div class="loading-spinner">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Loading candidates...</p>
            </div>
        `;

        const response = await fetch(`${API_BASE_URL}/candidates`);
        const data = await response.json();
        
        candidates = data.candidates || [];
        renderCandidates(candidates);
        
    } catch (error) {
        console.error('Error loading candidates:', error);
        candidatesGrid.innerHTML = `
            <div class="loading-spinner">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Error loading candidates</p>
            </div>
        `;
    }
}

function renderCandidates(candidateList) {
    const candidatesGrid = document.getElementById('candidatesGrid');
    
    if (candidateList.length === 0) {
        candidatesGrid.innerHTML = `
            <div class="loading-spinner">
                <i class="fas fa-users"></i>
                <p>No candidates found. Upload some resumes to get started!</p>
            </div>
        `;
        return;
    }

    candidatesGrid.innerHTML = candidateList.map(candidate => `
        <div class="candidate-card" onclick="showCandidateDetails('${candidate.name}')">
            <div class="candidate-header">
                <div class="candidate-avatar">
                    ${getInitials(candidate.name)}
                </div>
                <div class="candidate-info">
                    <h3>${candidate.name}</h3>
                    <p>${candidate.title || 'No title specified'}</p>
                </div>
            </div>
            <div class="candidate-skills">
                ${candidate.skills.slice(0, 5).map(skill => 
                    `<span class="skill-tag">${skill}</span>`
                ).join('')}
                ${candidate.skills.length > 5 ? `<span class="skill-tag">+${candidate.skills.length - 5} more</span>` : ''}
            </div>
        </div>
    `).join('');
}

function getInitials(name) {
    return name.split(' ').map(part => part[0]).join('').toUpperCase().slice(0, 2);
}

function filterCandidates() {
    const searchTerm = document.getElementById('candidateSearch').value.toLowerCase();
    
    const filtered = candidates.filter(candidate => 
        candidate.name.toLowerCase().includes(searchTerm) ||
        candidate.title.toLowerCase().includes(searchTerm) ||
        candidate.skills.some(skill => skill.toLowerCase().includes(searchTerm)) ||
        candidate.institutions.some(inst => inst.toLowerCase().includes(searchTerm))
    );
    
    renderCandidates(filtered);
}

async function showCandidateDetails(candidateName) {
    const modal = document.getElementById('candidateModal');
    const candidateNameEl = document.getElementById('candidateName');
    const candidateDetails = document.getElementById('candidateDetails');
    
    candidateNameEl.textContent = candidateName;
    candidateDetails.innerHTML = `
        <div class="loading-spinner">
            <i class="fas fa-spinner fa-spin"></i>
            <p>Loading candidate details...</p>
        </div>
    `;
    
    modal.classList.add('active');
    
    try {
        const response = await fetch(`${API_BASE_URL}/candidate/${encodeURIComponent(candidateName)}`);
        const candidate = await response.json();
        
        candidateDetails.innerHTML = `
            <div class="candidate-detail-section">
                <h4><i class="fas fa-user"></i> Basic Information</h4>
                <div class="detail-list">
                    <div><strong>Name:</strong> ${candidate.name}</div>
                    <div><strong>Title:</strong> ${candidate.title || 'Not specified'}</div>
                </div>
            </div>
            
            <div class="candidate-detail-section">
                <h4><i class="fas fa-cogs"></i> Skills</h4>
                <div class="candidate-skills">
                    ${candidate.skills.map(skill => `<span class="skill-tag">${skill}</span>`).join('')}
                </div>
            </div>
            
            <div class="candidate-detail-section">
                <h4><i class="fas fa-graduation-cap"></i> Education</h4>
                ${candidate.education.map(edu => `
                    <div class="education-item">
                        <h5>${edu.degree || 'Degree not specified'}</h5>
                        <p><strong>Institution:</strong> ${edu.institution}</p>
                        <p><strong>Year:</strong> ${edu.year || 'Not specified'}</p>
                    </div>
                `).join('')}
            </div>
            
            <div class="candidate-detail-section">
                <h4><i class="fas fa-project-diagram"></i> Projects</h4>
                ${candidate.projects.map(project => `
                    <div class="project-item">
                        <h5>${project.name}</h5>
                        <p><strong>Role:</strong> ${project.role || 'Not specified'}</p>
                        ${project.description ? `<p><strong>Description:</strong> ${project.description}</p>` : ''}
                        <div class="project-tech">
                            ${project.technologies.map(tech => `<span class="tech-tag">${tech}</span>`).join('')}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
        
    } catch (error) {
        console.error('Error loading candidate details:', error);
        candidateDetails.innerHTML = `
            <div class="loading-spinner">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Error loading candidate details</p>
            </div>
        `;
    }
}

function closeCandidateModal() {
    document.getElementById('candidateModal').classList.remove('active');
}

// Query System
function setQuery(query) {
    document.getElementById('queryInput').value = query;
}

async function submitQuery() {
    const queryInput = document.getElementById('queryInput');
    const queryResults = document.getElementById('queryResults');
    const submitButton = document.getElementById('querySubmit');
    
    const query = queryInput.value.trim();
    if (!query) {
        showToast('Please enter a query', 'warning');
        return;
    }

    submitButton.disabled = true;
    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Querying...';
    
    queryResults.innerHTML = `
        <div class="loading-spinner">
            <i class="fas fa-spinner fa-spin"></i>
            <p>Processing your query...</p>
        </div>
    `;
    queryResults.classList.remove('empty');

    try {
        const response = await fetch(`${API_BASE_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query })
        });

        const result = await response.json();
        
        if (result.success) {
            queryResults.innerHTML = `
                <h3>Query Results</h3>
                <p>${result.result}</p>
            `;
        } else {
            queryResults.innerHTML = `
                <h3>Error</h3>
                <p class="text-error">${result.error || 'Failed to process query'}</p>
            `;
        }
        
    } catch (error) {
        console.error('Query error:', error);
        queryResults.innerHTML = `
            <h3>Error</h3>
            <p class="text-error">Failed to connect to the server</p>
        `;
    } finally {
        submitButton.disabled = false;
        submitButton.innerHTML = '<i class="fas fa-search"></i> Query';
    }
}

// ATS Analysis
function toggleSingleResumeInput() {
    const singleInput = document.getElementById('singleResumeInput');
    const isVisible = singleInput.style.display !== 'none';
    singleInput.style.display = isVisible ? 'none' : 'block';
}

async function analyzeAllResumes() {
    const jobDescription = document.getElementById('jobDescription').value.trim();
    const atsResults = document.getElementById('atsResults');
    const analyzeButton = document.getElementById('analyzeAll');
    
    if (!jobDescription) {
        showToast('Please enter a job description', 'warning');
        return;
    }

    analyzeButton.disabled = true;
    analyzeButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
    
    atsResults.innerHTML = `
        <div class="loading-spinner">
            <i class="fas fa-spinner fa-spin"></i>
            <p>Analyzing all resumes against job description...</p>
        </div>
    `;
    atsResults.classList.remove('empty');

    try {
        const response = await fetch(`${API_BASE_URL}/ats-analysis`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ job_description: jobDescription })
        });

        const result = await response.json();
        
        if (result.success) {
            atsResults.innerHTML = `
                <h3>ATS Analysis Results</h3>
                <div class="ats-analysis-content">
                    <pre>${result.results}</pre>
                </div>
            `;
        } else {
            atsResults.innerHTML = `
                <h3>Error</h3>
                <p class="text-error">${result.error || 'Failed to analyze resumes'}</p>
            `;
        }
        
    } catch (error) {
        console.error('ATS analysis error:', error);
        atsResults.innerHTML = `
            <h3>Error</h3>
            <p class="text-error">Failed to connect to the server</p>
        `;
    } finally {
        analyzeButton.disabled = false;
        analyzeButton.innerHTML = '<i class="fas fa-chart-bar"></i> Analyze All Resumes';
    }
}

async function analyzeSingleResume() {
    const jobDescription = document.getElementById('jobDescription').value.trim();
    const resumeText = document.getElementById('singleResumeText').value.trim();
    const atsResults = document.getElementById('atsResults');
    const submitButton = document.getElementById('submitSingleATS');
    
    if (!jobDescription || !resumeText) {
        showToast('Please enter both job description and resume text', 'warning');
        return;
    }

    submitButton.disabled = true;
    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
    
    atsResults.innerHTML = `
        <div class="loading-spinner">
            <i class="fas fa-spinner fa-spin"></i>
            <p>Analyzing resume against job description...</p>
        </div>
    `;
    atsResults.classList.remove('empty');

    try {
        const response = await fetch(`${API_BASE_URL}/ats-single`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                job_description: jobDescription,
                resume_text: resumeText
            })
        });

        const result = await response.json();
        
        if (result.success) {
            const scoreClass = result.ats_score >= 70 ? 'high' : result.ats_score >= 40 ? 'medium' : 'low';
            
            atsResults.innerHTML = `
                <h3>Single Resume ATS Analysis</h3>
                <div class="ats-score-card">
                    <div class="ats-score-header">
                        <h4>ATS Analysis Results</h4>
                        <span class="score-badge ${scoreClass}">${result.ats_score}%</span>
                    </div>
                    
                    <div class="score-details">
                        <div class="score-metric">
                            <div class="value">${result.keyword_match_rate.toFixed(1)}%</div>
                            <div class="label">Keyword Match</div>
                        </div>
                        <div class="score-metric">
                            <div class="value">${result.matching_keywords.length}</div>
                            <div class="label">Matching Keywords</div>
                        </div>
                        <div class="score-metric">
                            <div class="value">${result.missing_keywords.length}</div>
                            <div class="label">Missing Keywords</div>
                        </div>
                    </div>
                    
                    <div class="candidate-detail-section">
                        <h4><i class="fas fa-check"></i> Matching Keywords</h4>
                        <div class="candidate-skills">
                            ${result.matching_keywords.map(keyword => `<span class="skill-tag">${keyword}</span>`).join('')}
                        </div>
                    </div>
                    
                    <div class="candidate-detail-section">
                        <h4><i class="fas fa-times"></i> Missing Keywords</h4>
                        <div class="candidate-skills">
                            ${result.missing_keywords.map(keyword => `<span class="skill-tag" style="background: rgba(239, 68, 68, 0.1); color: #ef4444;">${keyword}</span>`).join('')}
                        </div>
                    </div>
                    
                    <div class="candidate-detail-section">
                        <h4><i class="fas fa-lightbulb"></i> Recommendations</h4>
                        <ul class="detail-list">
                            ${result.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                        </ul>
                    </div>
                </div>
            `;
        } else {
            atsResults.innerHTML = `
                <h3>Error</h3>
                <p class="text-error">${result.error || 'Failed to analyze resume'}</p>
            `;
        }
        
    } catch (error) {
        console.error('Single ATS analysis error:', error);
        atsResults.innerHTML = `
            <h3>Error</h3>
            <p class="text-error">Failed to connect to the server</p>
        `;
    } finally {
        submitButton.disabled = false;
        submitButton.innerHTML = '<i class="fas fa-analyze"></i> Analyze';
    }
}

// Processing Status
async function loadProcessingStatus() {
    const processingSummary = document.getElementById('processingSummary');
    const processingDetails = document.getElementById('processingDetails');
    
    try {
        const response = await fetch(`${API_BASE_URL}/processing-status`);
        const status = await response.json();
        
        processingSummary.innerHTML = `
            <div class="summary-card">
                <div class="number">${status.processed_files}</div>
                <div class="label">Processed</div>
            </div>
            <div class="summary-card">
                <div class="number">${status.failed_files}</div>
                <div class="label">Failed</div>
            </div>
            <div class="summary-card">
                <div class="number">${status.processed_files + status.failed_files}</div>
                <div class="label">Total</div>
            </div>
        `;
        
        if (status.details.length > 0) {
            processingDetails.innerHTML = `
                <h4>Processing Details</h4>
                ${status.details.map(detail => `
                    <div class="processing-item ${detail.status}">
                        <div>
                            <strong>${detail.filename}</strong>
                            <div style="font-size: 0.9rem; color: #64748b;">
                                ${detail.processed_date} • ${detail.file_size} bytes
                            </div>
                            ${detail.error ? `<div style="font-size: 0.9rem; color: #ef4444;">Error: ${detail.error}</div>` : ''}
                        </div>
                        <div class="file-status ${detail.status}">
                            <i class="fas ${detail.status === 'processed' ? 'fa-check-circle' : 'fa-times-circle'}"></i>
                        </div>
                    </div>
                `).join('')}
            `;
        } else {
            processingDetails.innerHTML = '<p>No processing history found.</p>';
        }
        
    } catch (error) {
        console.error('Error loading processing status:', error);
        processingSummary.innerHTML = `
            <div class="loading-spinner">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Error loading processing status</p>
            </div>
        `;
    }
}

// Toast Notifications
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
            <i class="fas ${getToastIcon(type)}"></i>
            <span>${message}</span>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 5000);
}

function getToastIcon(type) {
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-times-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    return icons[type] || 'fa-info-circle';
}

// Auto-refresh functionality
setInterval(async () => {
    if (currentTab === 'status') {
        await checkSystemHealth();
        await loadProcessingStatus();
    }
}, 30000); // Refresh every 30 seconds when on status tab

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
            case '1':
                e.preventDefault();
                switchTab('upload');
                break;
            case '2':
                e.preventDefault();
                switchTab('candidates');
                break;
            case '3':
                e.preventDefault();
                switchTab('query');
                break;
            case '4':
                e.preventDefault();
                switchTab('ats');
                break;
            case '5':
                e.preventDefault();
                switchTab('status');
                break;
        }
    }
});

// Error handling for fetch requests
window.addEventListener('unhandledrejection', (e) => {
    console.error('Unhandled promise rejection:', e);
    showToast('An unexpected error occurred', 'error');
});

// Service worker registration for PWA capabilities (optional)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('SW registered: ', registration);
            })
            .catch(registrationError => {
                console.log('SW registration failed: ', registrationError);
            });
    });
}
