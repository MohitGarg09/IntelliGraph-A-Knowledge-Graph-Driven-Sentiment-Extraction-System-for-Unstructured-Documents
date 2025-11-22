from pdfminer.high_level import extract_text
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

# ========================
# RESUME PARSER FUNCTIONS
# ========================

def parse_resume(pdf_path):
    """Extract text from PDF resume"""
    try:
        text = extract_text(pdf_path)
        return text
    except Exception as e:
        print(f"Error parsing resume: {e}")
        return ""


def extract_entities_with_gemini(text):
    """Extract entities from resume text using Gemini AI"""
    try:
        generation_config = {
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        prompt = f"""
        Extract information in JSON format following this schema:
        {{
            "Person": {{"name": "", "title": ""}},
            "Contact": {{"email": "", "phone": ""}},
            "Skills": ["skill1", "skill2"],  
            "Education": [{{"degree": "", "institution": "", "year": ""}}],
            "Projects": [{{"name": "", "role": "", "technologies": [], "description": ""}}]
        }}
        
        Extract structured information from this resume:
        
        {text}
        
        Return only valid JSON.
        """
        response = model.generate_content(prompt)
        response_text = response.text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[-2].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[-2].strip()
        parsed_json = json.loads(response_text)
        return json.dumps(parsed_json)
    except Exception as e:
        print(f"Error extracting entities with Gemini: {e}")
        return "{}"

def setup_api_key():
    """Setup Google API key from environment variable or .env file"""
    load_dotenv()  # Load environment variables from .env file
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("No Google API key found. Please set GOOGLE_API_KEY in .env file")
        return False
    genai.configure(api_key=api_key)
    return True