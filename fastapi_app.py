from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import tempfile
import shutil
import asyncio
from contextlib import asynccontextmanager

# Import your existing modules
from database import Neo4jConnector
from resume_parser import setup_api_key, parse_resume, extract_entities_with_gemini
from knowledge_graph import create_knowledge_graph, create_person_connections
from rag_system import setup_rag_system, process_query
from resume_processor import process_resume_directory, get_resume_processing_status, calculate_resume_checksum
from ats_analyzer import query_ats_scores, calculate_ats_score

# Global variables to store system components
connector = None
graph = None
rag_system = None

# Pydantic models for request/response
class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    result: str
    success: bool
    error: Optional[str] = None

class ATSAnalysisRequest(BaseModel):
    job_description: str

class ATSAnalysisResponse(BaseModel):
    results: str
    success: bool
    error: Optional[str] = None

class SingleATSRequest(BaseModel):
    job_description: str
    resume_text: str

class SingleATSResponse(BaseModel):
    ats_score: int
    keyword_match_rate: float
    missing_keywords: List[str]
    matching_keywords: List[str]
    recommendations: List[str]
    success: bool
    error: Optional[str] = None

class ProcessingStatus(BaseModel):
    processed_files: int
    failed_files: int
    total_resumes: int
    processed_resumes: int
    pending_resumes: int
    failed_resumes: int
    details: List[Dict[str, Any]]
    recent_activity: List[str]
    success: bool = True

class HealthResponse(BaseModel):
    status: str
    neo4j_connected: bool
    rag_system_ready: bool
    api_key_configured: bool

class CandidatesResponse(BaseModel):
    candidates: List[Dict[str, Any]]
    total_count: int
    success: bool = True

async def initialize_system():
    """Initialize the resume analysis system"""
    global connector, graph, rag_system
    
    try:
        print("Initializing resume analysis system...")
        
        # Setup API key
        if not setup_api_key():
            raise Exception("Failed to setup Google API key")
        
        # Initialize Neo4j connection
        connector = Neo4jConnector()
        graph = connector.connect()
        
        # Setup RAG system
        rag_system = setup_rag_system(graph)
        if not rag_system:
            raise Exception("Failed to setup RAG system")
        
        print("System initialization complete!")
        return True
        
    except Exception as e:
        print(f"Error initializing system: {e}")
        return False

async def cleanup_system():
    """Cleanup system resources"""
    print("Shutting down resume analysis system...")
    # Add any cleanup logic here if needed

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    success = await initialize_system()
    if not success:
        raise Exception("Failed to initialize system")
    yield
    # Shutdown
    await cleanup_system()

# Create FastAPI app
app = FastAPI(
    title="Resume Analysis System API",
    description="API for analyzing resumes using Neo4j knowledge graphs and RAG",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware - FIXED: More permissive CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check system health"""
    try:
        neo4j_connected = connector and connector.graph is not None
        rag_ready = rag_system is not None
        api_configured = setup_api_key()  # This will return True if already configured
        
        status = "healthy" if all([neo4j_connected, rag_ready, api_configured]) else "unhealthy"
        
        return HealthResponse(
            status=status,
            neo4j_connected=neo4j_connected,
            rag_system_ready=rag_ready,
            api_key_configured=api_configured
        )
    except Exception as e:
        return HealthResponse(
            status="error",
            neo4j_connected=False,
            rag_system_ready=False,
            api_key_configured=False
        )

@app.post("/upload-resume")
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF resume file")
):
    """Upload and process a single resume"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_path = tmp_file.name
        
        # Process resume in background
        background_tasks.add_task(process_single_resume, tmp_path, file.filename)
        
        return {
            "message": f"Resume {file.filename} uploaded successfully and processing started",
            "filename": file.filename,
            "status": "processing",
            "success": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading resume: {str(e)}")

async def process_single_resume(file_path: str, original_filename: str):
    """Process a single resume file (background task)"""
    try:
        # Calculate checksum
        checksum = calculate_resume_checksum(file_path)
        file_size = os.path.getsize(file_path)
        
        # Check if already processed
        resume_exists_query = """
        MATCH (r:ResumeFile {checksum: $checksum})
        RETURN r.filename as filename
        """
        result = graph.run(resume_exists_query, checksum=checksum).data()
        
        if result:
            print(f"Resume {original_filename} already exists, skipping")
            os.unlink(file_path)  # Clean up temp file
            return
        
        # Parse resume
        resume_text = parse_resume(file_path)
        if not resume_text:
            raise Exception("Failed to extract text from resume")
        
        # Extract entities
        entities_json = extract_entities_with_gemini(resume_text)
        if entities_json == "{}":
            raise Exception("Failed to extract entities from resume")
        
        # Create tracking node
        tracking_query = """
        CREATE (r:ResumeFile {
            filename: $filename,
            checksum: $checksum,
            processed_date: datetime(),
            file_size: $file_size
        })
        """
        graph.run(tracking_query, 
                 filename=original_filename,
                 checksum=checksum,
                 file_size=file_size)
        
        # Create knowledge graph
        create_knowledge_graph(entities_json, connector, resume_path=file_path)
        
        # Update person connections
        create_person_connections(graph)
        
        print(f"Successfully processed {original_filename}")
        
    except Exception as e:
        print(f"Error processing {original_filename}: {str(e)}")
        # Log failure
        failure_query = """
        CREATE (f:FailedResume {
            filename: $filename,
            checksum: $checksum,
            error: $error,
            attempt_date: datetime()
        })
        """
        graph.run(failure_query,
                 filename=original_filename,
                 checksum=checksum,
                 error=str(e))
    finally:
        # Clean up temp file
        if os.path.exists(file_path):
            os.unlink(file_path)

@app.post("/upload-multiple-resumes")
async def upload_multiple_resumes(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="Multiple PDF resume files")
):
    """Upload and process multiple resumes"""
    pdf_files = [f for f in files if f.filename.endswith('.pdf')]
    
    if not pdf_files:
        raise HTTPException(status_code=400, detail="No valid PDF files found")
    
    try:
        temp_files = []
        for file in pdf_files:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                shutil.copyfileobj(file.file, tmp_file)
                temp_files.append((tmp_file.name, file.filename))
        
        # Process all resumes in background
        background_tasks.add_task(process_multiple_resumes, temp_files)
        
        return {
            "message": f"{len(pdf_files)} resumes uploaded successfully and processing started",
            "files": [f.filename for f in pdf_files],
            "status": "processing",
            "success": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading resumes: {str(e)}")

async def process_multiple_resumes(temp_files: List[tuple]):
    """Process multiple resume files (background task)"""
    for file_path, original_filename in temp_files:
        await process_single_resume(file_path, original_filename)

@app.post("/query", response_model=QueryResponse)
async def query_knowledge_graph(request: QueryRequest):
    """Query the knowledge graph using RAG"""
    try:
        if not rag_system:
            raise HTTPException(status_code=503, detail="RAG system not initialized")
        
        result = process_query(request.query, rag_system, graph)
        
        return QueryResponse(
            result=result,
            success=True
        )
        
    except Exception as e:
        return QueryResponse(
            result="",
            success=False,
            error=str(e)
        )

@app.post("/ats-analysis", response_model=ATSAnalysisResponse)
async def analyze_ats_scores(request: ATSAnalysisRequest):
    """Analyze ATS scores for all resumes against a job description"""
    try:
        result = query_ats_scores(request.job_description, graph, rag_system)
        
        return ATSAnalysisResponse(
            results=result,
            success=True
        )
        
    except Exception as e:
        return ATSAnalysisResponse(
            results="",
            success=False,
            error=str(e)
        )

@app.post("/ats-single", response_model=SingleATSResponse)
async def analyze_single_ats(request: SingleATSRequest):
    """Analyze ATS score for a single resume text"""
    try:
        result = calculate_ats_score(request.resume_text, request.job_description)
        
        return SingleATSResponse(
            ats_score=result.get("ats_score", 0),
            keyword_match_rate=result.get("keyword_match_rate", 0.0),
            missing_keywords=result.get("missing_keywords", []),
            matching_keywords=result.get("matching_keywords", []),
            recommendations=result.get("recommendations", []),
            success=True
        )
        
    except Exception as e:
        return SingleATSResponse(
            ats_score=0,
            keyword_match_rate=0.0,
            missing_keywords=[],
            matching_keywords=[],
            recommendations=[],
            success=False,
            error=str(e)
        )

@app.get("/processing-status", response_model=ProcessingStatus)
async def get_processing_status():
    """Get status of processed resumes"""
    try:
        # Get processed files
        processed_query = """
        MATCH (r:ResumeFile)
        RETURN r.filename as filename, 
               toString(r.processed_date) as processed_date,
               r.checksum as checksum,
               r.file_size as file_size,
               'processed' as status
        """
        processed_results = graph.run(processed_query).data()
        
        # Get failed files
        failed_query = """
        MATCH (f:FailedResume)
        RETURN f.filename as filename,
               toString(f.attempt_date) as processed_date,
               f.checksum as checksum,
               0 as file_size,
               'failed' as status,
               f.error as error
        """
        failed_results = graph.run(failed_query).data()
        
        all_details = processed_results + failed_results
        
        # Create recent activity list
        recent_activity = []
        for detail in all_details[-5:]:  # Last 5 items
            status = detail.get('status', 'unknown')
            filename = detail.get('filename', 'unknown')
            recent_activity.append(f"{status.capitalize()}: {filename}")
        
        return ProcessingStatus(
            processed_files=len(processed_results),
            failed_files=len(failed_results),
            total_resumes=len(all_details),
            processed_resumes=len(processed_results),
            pending_resumes=0,  # No pending tracking in current implementation
            failed_resumes=len(failed_results),
            details=all_details,
            recent_activity=recent_activity,
            success=True
        )
        
    except Exception as e:
        return ProcessingStatus(
            processed_files=0,
            failed_files=0,
            total_resumes=0,
            processed_resumes=0,
            pending_resumes=0,
            failed_resumes=0,
            details=[],
            recent_activity=[],
            success=False
        )

@app.get("/candidates", response_model=CandidatesResponse)
async def get_all_candidates():
    """Get all candidates in the system"""
    try:
        query = """
        MATCH (p:Person)
        OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
        OPTIONAL MATCH (p)-[:STUDIED_AT]->(i:Institution)
        OPTIONAL MATCH (p)-[:HAS_EMAIL]->(e:Email)
        OPTIONAL MATCH (p)-[:HAS_PHONE]->(ph:Phone)
        RETURN p.name as name, 
               p.title as title,
               collect(DISTINCT s.name) as skills,
               collect(DISTINCT i.name) as institutions,
               e.address as email,
               ph.number as phone
        ORDER BY p.name
        """
        results = graph.run(query).data()
        
        # Clean up the results
        candidates = []
        for result in results:
            candidate = {
                "name": result.get("name", "Unknown"),
                "title": result.get("title", "No title specified"),
                "skills": [skill for skill in result.get("skills", []) if skill],
                "institutions": [inst for inst in result.get("institutions", []) if inst],
                "email": result.get("email"),
                "phone": result.get("phone")
            }
            candidates.append(candidate)
        
        return CandidatesResponse(
            candidates=candidates,
            total_count=len(candidates),
            success=True
        )
        
    except Exception as e:
        print(f"Error in get_all_candidates: {str(e)}")
        return CandidatesResponse(
            candidates=[],
            total_count=0,
            success=False
        )

@app.get("/candidate/{name}")
async def get_candidate_details(name: str):
    """Get detailed information about a specific candidate"""
    try:
        # Get basic info
        basic_query = """
        MATCH (p:Person {name: $name})
        RETURN p.name as name, p.title as title
        """
        basic_result = graph.run(basic_query, name=name).data()
        
        if not basic_result:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        basic_info = basic_result[0]
        
        # Get skills
        skills_query = """
        MATCH (p:Person {name: $name})-[:HAS_SKILL]->(s:Skill)
        RETURN collect(s.name) as skills
        """
        skills_result = graph.run(skills_query, name=name).data()
        skills = skills_result[0]["skills"] if skills_result else []
        
        # Get education
        education_query = """
        MATCH (p:Person {name: $name})-[r:STUDIED_AT]->(i:Institution)
        RETURN collect({
            institution: i.name,
            degree: r.degree,
            year: r.year
        }) as education
        """
        education_result = graph.run(education_query, name=name).data()
        education = education_result[0]["education"] if education_result else []
        
        # Get projects
        projects_query = """
        MATCH (p:Person {name: $name})-[r:WORKED_ON]->(pr:Project)
        OPTIONAL MATCH (pr)-[:USES_TECHNOLOGY]->(t:Technology)
        RETURN collect(DISTINCT {
            name: pr.name,
            role: r.role,
            description: pr.description,
            technologies: collect(DISTINCT t.name)
        }) as projects
        """
        projects_result = graph.run(projects_query, name=name).data()
        projects = projects_result[0]["projects"] if projects_result else []
        
        return {
            "name": basic_info["name"],
            "title": basic_info["title"],
            "skills": skills,
            "education": education,
            "projects": projects,
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting candidate details: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)