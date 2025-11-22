# Resume Analysis System - Web UI

A modern, responsive web interface for the Resume Analysis System that provides an intuitive way to interact with your resume processing pipeline.

## Features

### 🚀 **Upload & Process Resumes**
- **Drag & Drop Interface**: Simply drag PDF files onto the upload area
- **Multiple File Upload**: Process multiple resumes simultaneously
- **Real-time Progress**: Visual feedback during upload and processing
- **Status Tracking**: Monitor processing success/failure for each file

### 👥 **Candidate Management**
- **Candidate Grid**: View all processed candidates in an organized layout
- **Search & Filter**: Find candidates by name, skills, title, or institution
- **Detailed Profiles**: Click any candidate to view comprehensive details including:
  - Skills and technologies
  - Education history
  - Project experience
  - Technology stack per project

### 🔍 **Intelligent Querying**
- **Natural Language Queries**: Ask questions in plain English
- **Example Queries**: Pre-built query templates for common searches
- **RAG-Powered Results**: Leverages the knowledge graph for accurate responses
- **Contextual Search**: Find candidates based on skills, experience, education, etc.

### 📊 **ATS Analysis**
- **Bulk Analysis**: Analyze all resumes against a job description
- **Single Resume Analysis**: Test individual resumes with detailed scoring
- **Comprehensive Metrics**:
  - Overall ATS score (0-100%)
  - Keyword match percentage
  - Missing vs. matching keywords
  - Specific improvement recommendations

### 📈 **System Monitoring**
- **Health Dashboard**: Real-time system status monitoring
- **Component Status**: Check Neo4j, RAG system, and API configuration
- **Processing History**: View all processed and failed resume attempts
- **Auto-refresh**: Status updates automatically every 30 seconds

## Quick Start

### 1. Start the FastAPI Backend
```bash
# Activate your virtual environment
acc-env\Scripts\activate

# Install dependencies (if not already done)
pip install -r requirements.txt

# Start the FastAPI server
python fastapi_app.py
```

The API will be available at `http://localhost:8000`

### 2. Open the Web UI
Simply open `index.html` in your web browser. The UI will automatically connect to the FastAPI backend.

### 3. System Requirements
Make sure these are running/configured:
- **Neo4j Database**: Running on `bolt://localhost:7687`
- **Google API Key**: Set in `.env` file as `GOOGLE_API_KEY`
- **FastAPI Server**: Running on `http://localhost:8000`

## UI Components

### Navigation Tabs
- **Upload Resumes**: File upload and processing
- **Candidates**: Browse and search candidates
- **Query System**: Natural language knowledge graph queries
- **ATS Analysis**: Resume-job matching analysis
- **Status**: System health and processing monitoring

### Key Features

#### Smart Upload System
- Validates PDF files only
- Prevents duplicate uploads using checksums
- Background processing with status updates
- Automatic candidate list refresh after processing

#### Advanced Search
- Real-time candidate filtering
- Search across names, skills, titles, and institutions
- Responsive grid layout with hover effects

#### Intelligent Query Interface
- Example queries for common use cases
- Ctrl+Enter keyboard shortcut for quick querying
- Formatted results with proper error handling

#### Comprehensive ATS Analysis
- Two analysis modes: bulk and single resume
- Visual score representation with color coding
- Detailed keyword analysis and recommendations
- Professional scoring metrics

## Technical Details

### Frontend Stack
- **HTML5**: Semantic markup with accessibility features
- **CSS3**: Modern styling with gradients, blur effects, and animations
- **Vanilla JavaScript**: No framework dependencies for lightweight performance
- **Font Awesome**: Icon library for consistent UI elements
- **Google Fonts**: Inter font family for modern typography

### API Integration
- **RESTful API**: Connects to FastAPI backend
- **Async Operations**: Non-blocking UI with proper loading states
- **Error Handling**: Comprehensive error handling with user feedback
- **Real-time Updates**: Polling for processing status updates

### Responsive Design
- **Mobile-First**: Optimized for all screen sizes
- **Flexible Grid**: Auto-adjusting layouts for different viewports
- **Touch-Friendly**: Large tap targets and intuitive gestures
- **Keyboard Navigation**: Full keyboard accessibility support

## Browser Compatibility
- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## Keyboard Shortcuts
- `Ctrl/Cmd + 1-5`: Switch between tabs
- `Ctrl/Cmd + Enter`: Submit query (when in query textarea)

## Troubleshooting

### Common Issues

1. **"System Issues" Status**
   - Check if Neo4j is running on port 7687
   - Verify Google API key is set in `.env` file
   - Ensure FastAPI server is running on port 8000

2. **Upload Failures**
   - Verify PDF files are not corrupted
   - Check file size limits
   - Ensure sufficient disk space

3. **Query Not Working**
   - Verify RAG system is initialized
   - Check if resumes have been processed
   - Ensure knowledge graph has data

4. **No Candidates Showing**
   - Upload and process some PDF resumes first
   - Check processing status for any failures
   - Verify Neo4j database connectivity

### Development Mode
For development, you can:
1. Open browser developer tools for debugging
2. Check console logs for detailed error messages
3. Monitor network tab for API request/response details
4. Use the health check endpoint to verify system status

## Future Enhancements
- Real-time WebSocket updates for processing status
- Advanced filtering and sorting options
- Resume comparison features
- Export functionality for analysis results
- Dark mode theme support
- Progressive Web App (PWA) capabilities
