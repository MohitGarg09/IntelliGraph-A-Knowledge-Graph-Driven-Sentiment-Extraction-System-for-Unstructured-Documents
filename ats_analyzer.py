import google.generativeai as genai
import json
import os
from resume_parser import parse_resume


def calculate_ats_score(resume_text, job_description):
    """Calculate ATS score by comparing resume against job description"""
    try:
        # Configure Gemini for ATS analysis
        generation_config = {
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            generation_config=generation_config
        )
        
        prompt = f"""
        Act as an ATS (Applicant Tracking System) analyzer. Compare the resume against the job description 
        and provide a detailed analysis in JSON format with the following structure:
        {{
            "ats_score": <score between 0-100> (to be given at must),
            "keyword_match_rate": <percentage of key terms found>,
            "missing_keywords": [<important keywords from job description not found in resume>],
            "matching_keywords": [<keywords found in both>],
            "recommendations": [<specific suggestions for improvement>]
        }}

        Job Description:
        {job_description}

        Resume Text:
        {resume_text}

        Base your analysis on:
        1. Keyword matching and relevance
        2. Required skills coverage
        3. Experience alignment
        4. Overall role fit
        
        Return only valid JSON.
        """
        
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Clean the response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        return json.loads(response_text)
        
    except Exception as e:
        print(f"Error calculating ATS score: {e}")
        return {
            "ats_score": 0,
            "keyword_match_rate": 0,
            "missing_keywords": [],
            "matching_keywords": [],
            "recommendations": [f"Error analyzing resume: {str(e)}"]
        }

# Add this function to query ATS scores
def query_ats_scores(job_description, graph, rag_system):
    """Query ATS scores for all resumes in the knowledge graph"""
    try:
        # Get all persons with their resume files
        person_query = """
        MATCH (p:Person)
        RETURN p.name as name, p.resume_file as resume_file
        """
        person_results = graph.run(person_query).data()
        
        ats_results = []
        for person in person_results:
            if person.get('resume_file'):
                resume_path = os.path.join("resumes", person['resume_file'])
                if os.path.exists(resume_path):
                    resume_text = parse_resume(resume_path)
                    if resume_text:
                        ats_score = calculate_ats_score(resume_text, job_description)
                        ats_results.append({
                            "name": person['name'],
                            "ats_analysis": ats_score
                        })
        
        # Use Gemini to generate a summary of the ATS analysis
        if ats_results:
            generation_config = {
                "temperature": 0.3,
                "max_output_tokens": 1024,
            }
            
            response_model = genai.GenerativeModel(
                model_name="gemini-2.5-flash-lite",
                generation_config=generation_config
            )
            
            summary_prompt = f"""
            Analyze these ATS results and provide a clear summary ranking the candidates.
            Focus on their match with the job requirements and specific strengths/weaknesses.

            Job Description:
            {job_description}

            ATS Results:
            {json.dumps(ats_results, indent=2)}

            Provide:
            1. Ranked list of candidates by ATS score only (0-100) no other text.
            2. Key strengths and gaps for each candidate
            
            """
            
            response = response_model.generate_content(summary_prompt)
            return response.text
        else:
            return "No resumes found in the system to analyze."
            
    except Exception as e:
        print(f"Error querying ATS scores: {e}")
        return f"Error analyzing resumes: {str(e)}"
