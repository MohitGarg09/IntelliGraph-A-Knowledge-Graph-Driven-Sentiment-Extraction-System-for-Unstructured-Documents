from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
import google.generativeai as genai
import json
import re
from knowledge_graph import normalize_entity_name

# ========================
# RAG SYSTEM FUNCTIONS
# ========================

def build_document_store_from_neo4j(graph):
    """Build document store from Neo4j knowledge graph"""
    documents = []
    try:
        # Query for all person details
        person_query = """
        MATCH (p:Person)
        RETURN p.name as name, p.title as title
        """
        person_results = graph.run(person_query).data()
        for person in person_results:
            doc_content = f"Person: {person['name']}, Title: {person['title']}"
            documents.append(Document(page_content=doc_content, metadata={"source": "knowledge_graph", "entity_type": "Person"}))
    
        # Query for skills per person
        skills_query = """
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        RETURN p.name as person, collect(s.name) as skills
        """
        skills_results = graph.run(skills_query).data()
        for record in skills_results:
            skills_list = ", ".join(record['skills'])
            doc_content = f"{record['person']} has the following skills: {skills_list}"
            documents.append(Document(page_content=doc_content, metadata={"source": "knowledge_graph", "entity_type": "Skills"}))
        
        # Query for education per person
        education_query = """
        MATCH (p:Person)-[r:STUDIED_AT]->(i:Institution)
        RETURN p.name as person, i.name as institution, r.degree as degree, r.year as year
        """
        education_results = graph.run(education_query).data()
        for edu in education_results:
            doc_content = f"{edu['person']} studied {edu['degree']} at {edu['institution']} ({edu['year']})"
            documents.append(Document(page_content=doc_content, metadata={"source": "knowledge_graph", "entity_type": "Education"}))
        
        # More comprehensive project query that captures all relationships
        projects_query = """
        MATCH (p:Person)-[r]->(pr)
        WHERE pr:Project OR (exists((pr)-[:USES_TECHNOLOGY]->()) AND NOT pr:Institution AND NOT pr:Skill AND NOT pr:Technology)
        RETURN p.name as person, pr.name as project, type(r) as relationship_type, 
               CASE WHEN r.role IS NOT NULL THEN r.role ELSE 'contributor' END as role, 
               CASE WHEN pr.description IS NOT NULL THEN pr.description ELSE '' END as description
        """
        projects_results = graph.run(projects_query).data()
        for proj in projects_results:
            rel_type = proj['relationship_type'].replace('_', ' ').lower()
            doc_content = f"{proj['person']} {rel_type} project '{proj['project']}' as {proj['role']}."
            if proj['description']:
                doc_content += f" Description: {proj['description']}"
            documents.append(Document(page_content=doc_content, metadata={"source": "knowledge_graph", "entity_type": "Project"}))
        
        # Direct project connections (an additional query to ensure all project links are captured)
        direct_project_query = """
        MATCH (p)-[r]-(n)
        WHERE n:Project 
        RETURN p.name as entity_name, labels(p) as entity_type, type(r) as relationship, n.name as project_name
        """
        direct_project_results = graph.run(direct_project_query).data()
        for conn in direct_project_results:
            entity_type = conn['entity_type'][0] if conn['entity_type'] else "Entity"
            rel_type = conn['relationship'].replace('_', ' ').lower()
            doc_content = f"{conn['entity_name']} ({entity_type}) {rel_type} project '{conn['project_name']}'"
            documents.append(Document(page_content=doc_content, metadata={"source": "knowledge_graph", "entity_type": "ProjectConnection"}))
        
        # Query for project technologies
        tech_query = """
        MATCH (pr:Project)-[:USES_TECHNOLOGY]->(t:Technology)
        RETURN pr.name as project, collect(t.name) as technologies
        """
        tech_results = graph.run(tech_query).data()
        for tech in tech_results:
            tech_list = ", ".join(tech['technologies'])
            doc_content = f"Project '{tech['project']}' uses the following technologies: {tech_list}"
            documents.append(Document(page_content=doc_content, metadata={"source": "knowledge_graph", "entity_type": "Technologies"}))
        
        # Technology to entity connections
        tech_connections_query = """
        MATCH (n)-[:USES_TECHNOLOGY]->(t:Technology)
        RETURN n.name as entity_name, labels(n) as entity_type, t.name as technology
        """
        tech_connections_results = graph.run(tech_connections_query).data()
        for conn in tech_connections_results:
            entity_type = conn['entity_type'][0] if conn['entity_type'] else "Entity"
            doc_content = f"{entity_type} '{conn['entity_name']}' uses technology '{conn['technology']}'"
            documents.append(Document(page_content=doc_content, metadata={"source": "knowledge_graph", "entity_type": "TechnologyConnection"}))
        
        # Query for person connections (people who studied together)
        studied_with_query = """
        MATCH (p1:Person)-[r:STUDIED_WITH]-(p2:Person)
        RETURN p1.name as person1, p2.name as person2, r.institution as institution
        """
        studied_with_results = graph.run(studied_with_query).data()
        for conn in studied_with_results:
            doc_content = f"{conn['person1']} and {conn['person2']} studied together at {conn['institution']}"
            documents.append(Document(page_content=doc_content, metadata={"source": "knowledge_graph", "entity_type": "Connection"}))
        
        # Query for person connections (people who worked together)
        worked_with_query = """
        MATCH (p1:Person)-[r:WORKED_WITH]-(p2:Person)
        RETURN p1.name as person1, p2.name as person2, r.project as project
        """
        worked_with_results = graph.run(worked_with_query).data()
        for conn in worked_with_results:
            doc_content = f"{conn['person1']} and {conn['person2']} worked together on project {conn['project']}"
            documents.append(Document(page_content=doc_content, metadata={"source": "knowledge_graph", "entity_type": "Connection"}))
        
        # Query for people with shared skills
        shared_skills_query = """
        MATCH (p1:Person)-[r:SHARES_SKILLS]-(p2:Person)
        RETURN p1.name as person1, p2.name as person2, r.skills as skills, r.count as count
        """
        shared_skills_results = graph.run(shared_skills_query).data()
        for conn in shared_skills_results:
            skills_list = ", ".join(conn['skills'][:5])  # Limit to first 5 skills for readability
            doc_content = f"{conn['person1']} and {conn['person2']} share {conn['count']} skills including: {skills_list}"
            documents.append(Document(page_content=doc_content, metadata={"source": "knowledge_graph", "entity_type": "Connection"}))
            
        return documents
    except Exception as e:
        print(f"Error building document store from Neo4j: {e}")
        return []


def setup_rag_system(graph):
    """Setup the RAG (Retrieval-Augmented Generation) system"""
    try:
        # Get documents from Neo4j
        documents = build_document_store_from_neo4j(graph)
        
        if not documents:
            print("No documents found in the knowledge graph.")
            return None
        
        # Create a hybrid retrieval system
        # 1. BM25 (keyword-based) retriever
        bm25_retriever = BM25Retriever.from_documents(documents)
        bm25_retriever.k = 5  # Return top 5 documents
          
        # 2. Vector-based retriever
        try:
            # Use sentence-transformers instead of Google embeddings
            # This is the key change to replace Google's embeddings
            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"  # A good compact model
            )
            vector_store = FAISS.from_documents(documents, embeddings)
            vector_retriever = vector_store.as_retriever(search_kwargs={"k": 5})
        except Exception as e:
            print(f"Error setting up vector retriever, falling back to BM25 only: {e}")
            vector_retriever = None
        
        return {
            "bm25_retriever": bm25_retriever,
            "vector_retriever": vector_retriever,
            "documents": documents
        }
    
    except Exception as e:
        print(f"Error setting up RAG system: {e}")
        return None


def normalize_query_entities(query):
    """Identify and normalize entity names in user queries for better matching"""
    try:
        # Configure the Gemini model for entity extraction
        generation_config = {
            "temperature": 0.1,
            "max_output_tokens": 512,
        }
        
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            generation_config=generation_config
        )
        
        prompt = f"""
        Extract entities from this query about resumes or job candidates. Return JSON with these fields:
        {{
          "institutions": [],  # Names of universities, colleges, etc.
          "skills": [],        # Technical skills or competencies
          "projects": [],      # Names of projects mentioned
          "technologies": [],  # Technologies or tools mentioned
          "names": []          # Names of people mentioned
        }}
        
        Query: "{query}"
        """
        
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Clean the response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        entities = json.loads(response_text)
        
        # Normalize each entity type
        normalized_entities = {
            "institutions": [normalize_entity_name(i, "Institution") for i in entities.get("institutions", [])],
            "skills": [normalize_entity_name(s, "Skill") for s in entities.get("skills", [])],
            "projects": [normalize_entity_name(p, "Project") for p in entities.get("projects", [])],
            "technologies": [normalize_entity_name(t, "Technology") for t in entities.get("technologies", [])],
            "names": entities.get("names", [])  # Don't normalize person names
        }
        
        # Add synonyms and variations for skills and technologies
        expanded_skills = set(normalized_entities["skills"])
        expanded_tech = set(normalized_entities["technologies"])
        
        # Add common synonyms for programming languages and frameworks
        skill_synonyms = {
            "js": "javascript",
            "py": "python",
            "ts": "typescript",
            "react": "reactjs",
            "vue": "vuejs",
            "ml": "machine learning",
            "ai": "artificial intelligence",
            "db": "database",
            "postgres": "postgresql",
            "react native": "reactnative",
            "node": "nodejs",
            "aws": "amazon web services",
            "frontend": "front-end",
            "backend": "back-end"
        }
        
        # Expand the skills and technologies with their synonyms
        for skill in list(expanded_skills):
            if skill in skill_synonyms:
                expanded_skills.add(skill_synonyms[skill])
        
        for tech in list(expanded_tech):
            if tech in skill_synonyms:
                expanded_tech.add(skill_synonyms[tech])
        
        normalized_entities["skills"] = list(expanded_skills)
        normalized_entities["technologies"] = list(expanded_tech)
        
        return normalized_entities
    
    except Exception as e:
        print(f"Error normalizing query entities: {e}")
        return {
            "institutions": [],
            "skills": [],
            "projects": [],
            "technologies": [],
            "names": []
        }


def process_query(query, rag_system, graph):
    """Process user query using RAG system and Neo4j graph"""
    try:
        if not rag_system:
            return "RAG system not initialized properly."
        
        # Normalize entities in the query
        normalized_entities = normalize_query_entities(query)
        
        # Extract potential person names from the query directly using regex
        # This helps catch names that might be missed by the entity extractor
        potential_names = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
        if potential_names:
            for name in potential_names:
                if name.lower() not in [n.lower() for n in normalized_entities["names"]]:
                    normalized_entities["names"].append(name)
        
        # Rewrite query to include normalized forms for better matching
        enhanced_query = query
        
        # Add normalized forms of institutions, skills, etc. to enhance retrieval
        if normalized_entities["institutions"]:
            enhanced_query += " Institutions: " + ", ".join(normalized_entities["institutions"])
        if normalized_entities["skills"]:
            enhanced_query += " Skills: " + ", ".join(normalized_entities["skills"])
        if normalized_entities["technologies"]:
            enhanced_query += " Technologies: " + ", ".join(normalized_entities["technologies"])
        if normalized_entities["projects"]:
            enhanced_query += " Projects: " + ", ".join(normalized_entities["projects"])
        if normalized_entities["names"]:
            enhanced_query += " Names: " + ", ".join(normalized_entities["names"])
        
        # Get documents from BM25 retriever
        bm25_docs = rag_system["bm25_retriever"].invoke(enhanced_query)
        
        # Get documents from vector retriever if available
        vector_docs = []
        if rag_system["vector_retriever"]:
            vector_docs = rag_system["vector_retriever"].invoke(enhanced_query)
        
        # Combine and deduplicate results
        all_docs = []
        doc_contents = set()
        
        for doc in bm25_docs + vector_docs:
            if doc.page_content not in doc_contents:
                all_docs.append(doc)
                doc_contents.add(doc.page_content)
        
        # Perform additional Neo4j queries for specific entity types if identified in the query
        additional_context = []
        
        # Handle queries about projects by person name more effectively
        # This is a crucial improvement for retrieving projects
        person_name_patterns = []
        for name in normalized_entities["names"]:
            # Create case-insensitive patterns and handle partial names
            name_parts = name.lower().split()
            for part in name_parts:
                if len(part) > 3:  # Only use name parts that are meaningful
                    person_name_patterns.append(f"(?i).*{part}.*")
        
        # If no names were extracted, check for name-like patterns in the query
        if not person_name_patterns and ("has" in query.lower() or "does" in query.lower() or 
                                        "by" in query.lower() or "of" in query.lower()):
            # Extract potential name from query context
            name_query = """
            MATCH (p:Person)
            WITH p.name as name
            RETURN name
            """
            all_names = [record["name"] for record in graph.run(name_query).data()]
            
            for name in all_names:
                name_parts = name.lower().split()
                for part in name_parts:
                    if len(part) > 3 and part.lower() in query.lower():
                        person_name_patterns.append(f"(?i).*{part}.*")
                        break
        
        # Direct project query for people mentioned in the query
        if person_name_patterns and ("project" in query.lower() or "worked on" in query.lower() or 
                                     "developed" in query.lower() or "created" in query.lower() or
                                     "built" in query.lower()):
            project_query = """
            MATCH (p:Person)-[r:WORKED_ON]->(pr:Project)
            WHERE any(pattern IN $patterns WHERE p.name =~ pattern)
            RETURN p.name as person, pr.name as project, r.role as role, pr.description as description
            """
            
            project_results = graph.run(project_query, patterns=person_name_patterns).data()
            
            if project_results:
                for result in project_results:
                    project_desc = result.get('description', '')
                    context = f"{result['person']} worked on project '{result['project']}' as {result['role']}."
                    if project_desc:
                        context += f" Description: {project_desc}"
                    additional_context.append(context)
                    
                    # Also fetch technologies used in these projects
                    tech_query = """
                    MATCH (pr:Project {name: $project_name})-[:USES_TECHNOLOGY]->(t:Technology)
                    RETURN collect(t.name) as technologies
                    """
                    tech_result = graph.run(tech_query, project_name=result['project']).data()
                    if tech_result and tech_result[0]['technologies']:
                        tech_list = ", ".join(tech_result[0]['technologies'])
                        additional_context.append(f"Project '{result['project']}' uses: {tech_list}")
            else:
                # If no project found through WORKED_ON, check if the person exists
                person_check_query = """
                MATCH (p:Person)
                WHERE any(pattern IN $patterns WHERE p.name =~ pattern)
                RETURN p.name as person
                """
                person_result = graph.run(person_check_query, patterns=person_name_patterns).data()
                
                if person_result:
                    person_name = person_result[0]['person']
                    # Check for other relationships that might connect to projects
                    alt_project_query = """
                    MATCH (p:Person {name: $person_name})-[r]-(n)
                    WHERE n:Project OR EXISTS((n)-[:USES_TECHNOLOGY]->())
                    RETURN distinct n.name as related_entity, labels(n) as types
                    """
                    alt_results = graph.run(alt_project_query, person_name=person_name).data()
                    
                    if alt_results:
                        for result in alt_results:
                            entity_type = result['types'][0] if result['types'] else "Entity"
                            additional_context.append(f"{person_name} is connected to {entity_type} '{result['related_entity']}'")
                    else:
                        additional_context.append(f"No project information found for {person_name} in the knowledge graph.")
        
        # If specific skills are mentioned, find people with those skills
        if normalized_entities["skills"] or normalized_entities["technologies"]:
            combined_skills = normalized_entities["skills"] + normalized_entities["technologies"]
            if combined_skills:
                # Use Cypher's regular expression matching for fuzzy skill matching
                skill_patterns = [f"(?i).*{skill}.*" for skill in combined_skills]
                
                skill_query = """
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
                WHERE any(pattern IN $patterns WHERE s.name =~ pattern)
                WITH p, collect(s.name) as matchedSkills
                RETURN p.name as person, p.title as title, matchedSkills, size(matchedSkills) as skillCount
                ORDER BY skillCount DESC
                LIMIT 5
                """
                skill_results = graph.run(skill_query, patterns=skill_patterns).data()
                
                for result in skill_results:
                    skills_str = ", ".join(result["matchedSkills"])
                    context = f"{result['person']} ({result['title']}) has the following requested skills: {skills_str}"
                    additional_context.append(context)
        
        # If institutions are mentioned, find people who studied there
        if normalized_entities["institutions"]:
            institution_patterns = [f"(?i).*{inst}.*" for inst in normalized_entities["institutions"]]
            
            institution_query = """
            MATCH (p:Person)-[r:STUDIED_AT]->(i:Institution)
            WHERE any(pattern IN $patterns WHERE i.name =~ pattern)
            RETURN p.name as person, i.name as institution, r.degree as degree, r.year as year
            LIMIT 5
            """
            institution_results = graph.run(institution_query, patterns=institution_patterns).data()
            
            for result in institution_results:
                context = f"{result['person']} studied {result['degree']} at {result['institution']} ({result['year']})"
                additional_context.append(context)
        
        # If specific people are mentioned, find their connections
        if normalized_entities["names"]:
            name_patterns = [f"(?i).*{name}.*" for name in normalized_entities["names"]]
            
            connection_query = """
            MATCH (p1:Person)-[r]-(p2:Person)
            WHERE any(pattern IN $patterns WHERE p1.name =~ pattern OR p2.name =~ pattern)
            RETURN p1.name as person1, type(r) as relationship, p2.name as person2
            LIMIT 10
            """
            connection_results = graph.run(connection_query, patterns=name_patterns).data()
            
            for result in connection_results:
                rel_type = result["relationship"].replace("_", " ").lower()
                context = f"{result['person1']} {rel_type} {result['person2']}"
                additional_context.append(context)
        
        # If projects are mentioned, find people who worked on them
        if normalized_entities["projects"]:
            project_patterns = [f"(?i).*{proj}.*" for proj in normalized_entities["projects"]]
            
            project_query = """
            MATCH (p:Person)-[r:WORKED_ON]->(pr:Project)
            WHERE any(pattern IN $patterns WHERE pr.name =~ pattern)
            RETURN p.name as person, pr.name as project, r.role as role, pr.description as description
            LIMIT 5
            """
            project_results = graph.run(project_query, patterns=project_patterns).data()
            
            for result in project_results:
                context = f"{result['person']} worked on project '{result['project']}' as {result['role']}"
                if result.get('description'):
                    context += f". Description: {result['description']}"
                additional_context.append(context)
        
        # Prepare the context from retrieved documents and additional Neo4j queries
        context = "\n".join([doc.page_content for doc in all_docs])
        if additional_context:
            context += "\n" + "\n".join(additional_context)
        
        # If no relevant context was found and it's a project query, do a broader search
        if not context.strip() and ("project" in query.lower() or "worked on" in query.lower()):
            # Get all projects in the graph with their descriptions
            all_projects_query = """
            MATCH (pr:Project)<-[:WORKED_ON]-(p:Person)
            RETURN p.name as person, pr.name as project, pr.description as description
            LIMIT 10
            """
            all_projects = graph.run(all_projects_query).data()
            
            if all_projects:
                context += "\nHere are some projects from the knowledge graph:\n"
                for proj in all_projects:
                    desc = proj.get('description', 'No description available')
                    context += f"{proj['person']} worked on {proj['project']}. {desc}\n"
        
        # Use Gemini to generate a response based on the retrieved information
        generation_config = {
            "temperature": 0.3,
            "max_output_tokens": 1024,
        }
        
        response_model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            generation_config=generation_config
        )
        
        prompt = f"""
        You are an HR assistant that helps with querying a knowledge graph built from resumes.
        Answer the following question based on the retrieved information.
        If the information doesn't contain the answer, explicitly state what's missing and what information you were able to find.
        
        Retrieved Information:
        {context}
        
        Question: {query}
        
        Give a concise and helpful answer. If project information is requested but not found for a specific person, 
        explicitly mention that project details appear to be missing for that person in the knowledge graph.
        """
        
        # Generate the response
        response = response_model.generate_content(prompt)
        
        return response.text
    
    except Exception as e:
        print(f"Error processing query: {e}")
        return f"Error processing query: {str(e)}"

