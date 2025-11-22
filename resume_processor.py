import os
import glob
import hashlib
import time
import traceback
from datetime import datetime
import json
from py2neo import Graph
from PyPDF2 import PdfReader  
import google.generativeai as genai
from resume_parser import parse_resume, extract_entities_with_gemini, setup_api_key
from knowledge_graph import create_knowledge_graph, create_person_connections


# Add this after the existing utility functions
def calculate_resume_checksum(file_path):
    """Calculate SHA-256 checksum of a file"""
    import hashlib
    
    try:
        with open(file_path, "rb") as f:
            bytes = f.read()
            return hashlib.sha256(bytes).hexdigest()
    except Exception as e:
        print(f"Error calculating checksum: {e}")
        return None


def process_resume_directory(directory_path, connector, max_retries=3):
    """Process all PDF resumes in a directory with checksum verification"""
    try:
        print("\nChecking directory for PDF files...")
        pdf_files = glob.glob(os.path.join(directory_path, "*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in {directory_path}")
            return False
        
        print(f"Found {len(pdf_files)} PDF files")
        
        # Setup resume tracking in Neo4j
        print("Setting up resume tracking in Neo4j...")
        if not setup_resume_tracking(connector.graph):
            print("Failed to setup resume tracking")
            return False
        
        for pdf_path in pdf_files:
            filename = os.path.basename(pdf_path)
            print(f"\nProcessing resume: {filename}")
            
            try:
                # Verify file exists and is readable
                if not os.path.isfile(pdf_path):
                    print(f"File not found: {pdf_path}")
                    continue
                    
                # Check file size
                file_size = os.path.getsize(pdf_path)
                if file_size == 0:
                    print(f"Error: {filename} is empty")
                    continue
                    
                print(f"File size: {file_size} bytes")
                
                # Calculate checksum
                print("Calculating checksum...")
                checksum = calculate_resume_checksum(pdf_path)
                if not checksum:
                    print(f"Failed to calculate checksum for {filename}")
                    continue
                
                print(f"Checksum: {checksum}")
                
                # Check if resume already processed
                print("Checking if resume was previously processed...")
                resume_exists_query = """
                MATCH (r:ResumeFile {checksum: $checksum})
                RETURN r.filename as filename, 
                       toString(r.processed_date) as processed_date
                """
                result = connector.graph.run(resume_exists_query, checksum=checksum).data()
                
                if result:
                    processed_date = result[0].get('processed_date', 'Unknown date')
                    print(f"Resume {filename} already processed on {processed_date}")
                    print(f"Skipping duplicate file (previously processed as {result[0]['filename']})")
                    continue
                
                # Process new resume
                retry_count = 0
                success = False
                last_error = None
                
                while retry_count < max_retries and not success:
                    try:
                        print(f"Attempt {retry_count + 1}: Parsing resume text...")
                        resume_text = parse_resume(pdf_path)
                        if not resume_text:
                            raise Exception("Failed to extract text from resume")
                        
                        print("Extracting entities with Gemini...")
                        entities_json = extract_entities_with_gemini(resume_text)
                        if entities_json == "{}":
                            raise Exception("Failed to extract entities from resume text")
                        
                        print("Creating resume tracking node...")
                        tracking_query = """
                        CREATE (r:ResumeFile {
                            filename: $filename,
                            checksum: $checksum,
                            processed_date: datetime(),
                            file_size: $file_size
                        })
                        """
                        connector.graph.run(tracking_query, 
                                         filename=filename,
                                         checksum=checksum,
                                         file_size=file_size)
                        
                        print("Creating knowledge graph nodes...")
                        create_knowledge_graph(entities_json, connector, resume_path=pdf_path)
                        print(f"Successfully processed {filename}")
                        success = True
                        break
                        
                    except Exception as e:
                        last_error = e
                        retry_count += 1
                        print(f"Attempt {retry_count} failed with error: {str(e)}")
                        traceback.print_exc()
                        if retry_count < max_retries:
                            print(f"Retrying in 2 seconds...")
                            time.sleep(2)
                        else:
                            print(f"Failed to process {filename} after {max_retries} attempts")
                            print(f"Last error: {str(last_error)}")
                            
                            # Log failed processing
                            failure_query = """
                            CREATE (f:FailedResume {
                                filename: $filename,
                                checksum: $checksum,
                                error: $error,
                                attempt_date: datetime()
                            })
                            """
                            connector.graph.run(failure_query,
                                             filename=filename,
                                             checksum=checksum,
                                             error=str(last_error))
                            
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")
                traceback.print_exc()
                continue
        
        print("\nCreating person connections...")
        create_person_connections(connector.graph)
        return True
        
    except Exception as e:
        print(f"Error in process_resume_directory: {str(e)}")
        traceback.print_exc()
        return False

def get_resume_processing_status(graph):
    """Get status of all processed and failed resumes"""
    try:
        status_query = """
        MATCH (r:ResumeFile)
        RETURN r.filename as filename, 
               r.processed_date as processed_date,
               r.checksum as checksum
        UNION
        MATCH (f:FailedResume)
        RETURN f.filename as filename,
               f.attempt_date as processed_date,
               f.checksum as checksum
        """
        
        results = graph.run(status_query).data()
        return results
    except Exception as e:
        print(f"Error getting resume status: {e}")
        return []

def setup_resume_tracking(graph):
    """Setup Neo4j constraints and indexes for resume tracking"""
    try:
        # Create constraints and indexes if they don't exist
        constraints = [
            "CREATE CONSTRAINT resume_checksum_unique IF NOT EXISTS FOR (r:ResumeFile) REQUIRE r.checksum IS UNIQUE",
            "CREATE INDEX resume_file_name_idx IF NOT EXISTS FOR (r:ResumeFile) ON (r.filename)"
        ]
        
        for constraint in constraints:
            graph.run(constraint)
            
        return True
    except Exception as e:
        print(f"Error setting up resume tracking: {e}")
        return False
