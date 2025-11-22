from database import Neo4jConnector
from resume_parser import setup_api_key, parse_resume
from knowledge_graph import create_knowledge_graph, create_person_connections
from rag_system import setup_rag_system, process_query
from resume_processor import process_resume_directory, get_resume_processing_status
from ats_analyzer import query_ats_scores
import os
import traceback

# ========================
# MAIN FUNCTION
# ========================

def main():
    """Main function to run the resume analysis system"""
    try:
        # Setup API key first
        if not setup_api_key():
            return
        
        # Initialize Neo4j connection with retry mechanism
        connector = Neo4jConnector()
        retry_count = 0
        max_retries = 3
        while retry_count < max_retries:
            try:
                graph = connector.connect()
                break
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    print(f"Connection attempt {retry_count} failed, retrying... ({str(e)})")
                else:
                    print(f"Failed to connect to Neo4j after {max_retries} attempts")
                    return
        
        resume_dir = "resumes"
        if not os.path.exists(resume_dir):
            os.makedirs(resume_dir)
            print(f"Created directory: {resume_dir}")
            print("Please add PDF resumes to this directory and run again.")
            return
            
        success = process_resume_directory(resume_dir, connector)
        if not success:
            print("Failed to process resumes.")
            return
            
        rag_system = setup_rag_system(graph)
        if not rag_system:
            print("Failed to set up RAG system.")
            return
            
        print("\nResume Analysis System Ready!")
        print("Available options:")
        print("1. Query knowledge graph")
        print("2. Run ATS analysis")
        print("3. Show resume processing status")
        print("4. Exit")
        
        while True:
            try:
                print("\nOptions:")
                print("1. Query knowledge graph")
                print("2. Run ATS analysis")
                print("3. Show resume processing status")
                print("4. Exit")
                
                choice = input("\nEnter your choice (1-4): ")
                
                if choice == "4":
                    break
                                # Inside main function, replace the elif choice == "3" section with:
                elif choice == "3":
                    print("\nResume Processing Status:")
                    try:
                        # Modified query to handle datetime conversion in Neo4j
                        status_query = """
                        MATCH (r:ResumeFile)
                        RETURN r.filename as filename, 
                            toString(r.processed_date) as processed_date,
                            r.checksum as checksum,
                            r.file_size as file_size
                        UNION
                        MATCH (f:FailedResume)
                        RETURN f.filename as filename,
                            toString(f.attempt_date) as processed_date,
                            f.checksum as checksum,
                            0 as file_size
                        """
                        
                        status_results = graph.run(status_query).data()
                        
                        if status_results:
                            print("\nProcessed Resumes:")
                            for entry in status_results:
                                print("\nFile:", entry['filename'])
                                print("Processed Date:", entry['processed_date'])
                                print("File Size:", f"{entry['file_size']} bytes")
                                print("Checksum:", entry['checksum'])
                        else:
                            print("No resume processing history found.")
                            
                        # Check for failed processing attempts
                        failed_query = """
                        MATCH (f:FailedResume)
                        RETURN f.filename as filename, 
                            toString(f.attempt_date) as attempt_date,
                            f.error as error
                        """
                        failed_results = graph.run(failed_query).data()
                        
                        if failed_results:
                            print("\nFailed Processing Attempts:")
                            for failed in failed_results:
                                print("\nFile:", failed['filename'])
                                print("Attempt Date:", failed['attempt_date'])
                                print("Error:", failed['error'])
                                
                    except Exception as e:
                        print(f"Error retrieving processing status: {str(e)}")
                        traceback.print_exc()
                        print("Please check Neo4j connection and database status.")
                elif choice == "2":
                    job_description = input("\nPlease paste the job description: ")
                    print("\nAnalyzing resumes against job description...")
                    result = query_ats_scores(job_description, graph, rag_system)
                    print("\nATS Analysis Results:")
                    print(result)
                elif choice == "1":
                    query = input("\nEnter your query: ")
                    result = process_query(query, rag_system, graph)
                    print("\nResult:")
                    print(result)
                else:
                    print("Invalid choice. Please try again.")
                    
            except Exception as e:
                print(f"Error processing request: {str(e)}")
                
        print("Goodbye!")
        
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        
if __name__ == "__main__":
    main()