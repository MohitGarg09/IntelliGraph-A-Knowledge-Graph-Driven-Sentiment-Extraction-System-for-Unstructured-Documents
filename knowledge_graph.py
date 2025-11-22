from py2neo import Node, Relationship
import re
from difflib import SequenceMatcher
import json
import google.generativeai as genai
from py2neo import NodeMatcher
import os


# ========================
# KNOWLEDGE GRAPH FUNCTIONS
# ========================

def normalize_entity_name(name, entity_type):
    """Normalize entity names for better matching"""
    if not name:
        return "Unknown"
    normalized = name.lower().strip()
    if entity_type == "Institution":
        normalized = re.sub(r',\s*[a-z\s]+$', '', normalized)
        normalized = re.sub(r'\([a-z\s]+\)$', '', normalized)
        for filler in [" the ", " of ", " & "]:
            normalized = normalized.replace(filler, " ")
        for suffix in [" university", " college", " institute", " school"]:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
    elif entity_type == "Skill" or entity_type == "Technology":
        normalized = re.sub(r'(\b[a-z]+)[\s\-]?(\d+(\.\d+)?)', r'\1', normalized)
        for qualifier in [" programming", " language", " framework", " development"]:
            normalized = normalized.replace(qualifier, "")
    elif entity_type == "Project":
        for descriptor in [" project", " system", " application", " platform"]:
            normalized = normalized.replace(descriptor, "")
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def find_similar_node(matcher, label, name, similarity_threshold=0.85):
    """Find similar nodes using fuzzy matching"""
    node = matcher.match(label, name=name).first()
    if node:
        return node
    query = f"MATCH (n:{label}) RETURN n.name as name"
    results = matcher.graph.run(query).data()
    for result in results:
        existing_name = result["name"]
        normalized_existing = normalize_entity_name(existing_name, label)
        normalized_new = normalize_entity_name(name, label)
        similarity = SequenceMatcher(None, normalized_existing, normalized_new).ratio()
        if similarity >= similarity_threshold:
            return matcher.match(label, name=existing_name).first()
    return None


def create_knowledge_graph(extracted_entities_json, connector, resume_path=""):
    """Create knowledge graph from extracted entities"""
    try:
        # Get Neo4j graph instance
        graph = connector.graph
        if not graph:
            raise ValueError("No active Neo4j connection")
        
        # Parse the JSON string into a dictionary
        entities = json.loads(extracted_entities_json)
        
        # Create matcher for finding existing nodes
        matcher = NodeMatcher(graph)
        
        # Convert projects data from Experience if needed
        if "Projects" not in entities and "Experience" in entities:
            entities["Projects"] = []
            for exp in entities["Experience"]:
                project = {
                    "name": exp.get("company", "Unknown Project"),
                    "role": exp.get("role", ""),
                    "technologies": [],  # We'll infer these from the description later
                    "description": exp.get("description", "")
                }
                entities["Projects"].append(project)
        
        # Create person node
        person_name = entities.get("Person", {}).get("name", "Unknown")
        person_title = entities.get("Person", {}).get("title", "")
        
        # Check if person already exists
        person_node = matcher.match("Person", name=person_name).first()
        if not person_node:
            person_node = Node("Person", name=person_name, title=person_title)
            # If we have a resume file path, store the filename for reference
            if resume_path:
                person_node["resume_file"] = os.path.basename(resume_path)
            graph.create(person_node)
        
        # Add contact information
        if "Contact" in entities:
            contact_data = entities["Contact"]
            if "email" in contact_data:
                email_node = Node("Email", address=contact_data["email"])
                has_email = Relationship(person_node, "HAS_EMAIL", email_node)
                graph.create(email_node)
                graph.create(has_email)
            
            if "phone" in contact_data:
                phone_node = Node("Phone", number=contact_data["phone"])
                has_phone = Relationship(person_node, "HAS_PHONE", phone_node)
                graph.create(phone_node)
                graph.create(has_phone)
        
        # Add skills with entity resolution
        for skill in entities.get("Skills", []):
            # Use fuzzy matching to find similar skill nodes
            skill_node = find_similar_node(matcher, "Skill", skill)
            
            if not skill_node:
                # Create new skill node if no similar one exists
                skill_node = Node("Skill", name=skill)
                graph.create(skill_node)
            
            # Check if relationship already exists
            rel_exists = graph.run(
                "MATCH (p:Person {name: $person_name})-[r:HAS_SKILL]->(s:Skill {name: $skill_name}) "
                "RETURN count(r) > 0 as exists", 
                person_name=person_name, skill_name=skill_node["name"]
            ).evaluate()
            
            if not rel_exists:
                has_skill = Relationship(person_node, "HAS_SKILL", skill_node)
                graph.create(has_skill)
        
        # Add education with entity resolution
        for edu in entities.get("Education", []):
            institution_name = edu.get("institution", "Unknown Institution")
            
            # Use fuzzy matching to find similar institution nodes
            institution_node = find_similar_node(matcher, "Institution", institution_name)
            
            if not institution_node:
                # Create new institution node if no similar one exists
                institution_node = Node("Institution", name=institution_name)
                # Also store the normalized name for future matching
                normalized_name = normalize_entity_name(institution_name, "Institution")
                if normalized_name != institution_name.lower().strip():
                    institution_node["normalized_name"] = normalized_name
                graph.create(institution_node)
            
            # Create education relationship with properties
            rel_exists = graph.run(
                "MATCH (p:Person {name: $person_name})-[r:STUDIED_AT]->(i:Institution {name: $institution_name}) "
                "RETURN count(r) > 0 as exists", 
                person_name=person_name, institution_name=institution_node["name"]
            ).evaluate()
            
            if not rel_exists:
                studied_at = Relationship(
                    person_node, "STUDIED_AT", institution_node,
                    degree=edu.get("degree", ""),
                    year=edu.get("year", "")
                )
                graph.create(studied_at)
        
        # Add projects with entity resolution
        for project in entities.get("Projects", []):
            project_name = project.get("name", "Unknown Project")
            
            # Use fuzzy matching to find similar project nodes
            project_node = find_similar_node(matcher, "Project", project_name, similarity_threshold=0.9)
            
            if not project_node:
                # Create new project node if no similar one exists
                project_node = Node("Project", 
                                  name=project_name,
                                  description=project.get("description", ""))
                # Also store the normalized name for future matching
                normalized_name = normalize_entity_name(project_name, "Project")
                if normalized_name != project_name.lower().strip():
                    project_node["normalized_name"] = normalized_name
                graph.create(project_node)
            
            # Create project relationship
            rel_exists = graph.run(
                "MATCH (p:Person {name: $person_name})-[r:WORKED_ON]->(pr:Project {name: $project_name}) "
                "RETURN count(r) > 0 as exists", 
                person_name=person_name, project_name=project_node["name"]
            ).evaluate()
            
            if not rel_exists:
                worked_on = Relationship(
                    person_node, "WORKED_ON", project_node,
                    role=project.get("role", "")
                )
                graph.create(worked_on)
            
            # Extract technologies from project description if not provided
            technologies = project.get("technologies", [])
            if not technologies and project.get("description"):
                # Use Gemini to extract technologies from description
                try:
                    generation_config = {
                        "temperature": 0.1,
                        "max_output_tokens": 256,
                    }
                    
                    tech_model = genai.GenerativeModel(
                        model_name="gemini-2.5-flash-lite",
                        generation_config=generation_config
                    )
                    
                    tech_prompt = f"""
                    Extract all technologies, programming languages, frameworks, and tools mentioned in the text.
                    Return only a JSON array of strings.
                    
                    Text: {project.get("description", "")}
                    """
                    
                    tech_response = tech_model.generate_content(tech_prompt)
                    tech_text = tech_response.text
                    
                    # Clean the response
                    if "```json" in tech_text:
                        tech_text = tech_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in tech_text:
                        tech_text = tech_text.split("```")[1].split("```")[0].strip()
                        
                    tech_json = json.loads(tech_text)
                    if isinstance(tech_json, dict) and "technologies" in tech_json:
                        technologies = tech_json["technologies"]
                    elif isinstance(tech_json, list):
                        technologies = tech_json
                except Exception as e:
                    print(f"Error extracting technologies: {e}")
            
            # Add technologies to the graph with entity resolution
            for tech in technologies:
                # Use fuzzy matching to find similar technology nodes
                tech_node = find_similar_node(matcher, "Technology", tech)
                
                if not tech_node:
                    # Create new technology node if no similar one exists
                    tech_node = Node("Technology", name=tech)
                    # Also store the normalized name for future matching
                    normalized_name = normalize_entity_name(tech, "Technology")
                    if normalized_name != tech.lower().strip():
                        tech_node["normalized_name"] = normalized_name
                    graph.create(tech_node)
                
                # Create relationship between project and technology
                rel_exists = graph.run(
                    "MATCH (pr:Project {name: $project_name})-[r:USES_TECHNOLOGY]->(t:Technology {name: $tech_name}) "
                    "RETURN count(r) > 0 as exists", 
                    project_name=project_node["name"], tech_name=tech_node["name"]
                ).evaluate()
                
                if not rel_exists:
                    uses_tech = Relationship(project_node, "USES_TECHNOLOGY", tech_node)
                    graph.create(uses_tech)
                
        return graph
    
    except Exception as e:
        print(f"Error creating knowledge graph: {e}")
        return None


def create_person_connections(graph):
    """Create connections between people based on shared attributes"""
    try:
        # Connect people who studied at the same institution (using improved matching)
        same_institution_query = """
        MATCH (p1:Person)-[r1:STUDIED_AT]->(i1:Institution)
        MATCH (p2:Person)-[r2:STUDIED_AT]->(i2:Institution)
        WHERE p1.name <> p2.name
        AND NOT (p1)-[:STUDIED_WITH]-(p2)
        AND (
            i1.name = i2.name OR
            (i1.normalized_name IS NOT NULL AND i2.normalized_name IS NOT NULL AND i1.normalized_name = i2.normalized_name)
        )
        RETURN p1, p2, i1.name as institution
        """
        same_institution_results = graph.run(same_institution_query).data()
        
        for result in same_institution_results:
            p1 = result['p1']
            p2 = result['p2']
            institution = result['institution']
            studied_with = Relationship(p1, "STUDIED_WITH", p2, institution=institution)
            graph.create(studied_with)
            print(f"Connected {p1['name']} and {p2['name']} who studied at {institution}")
        
        # Connect people who worked on similarly named projects (using normalized names)
        similar_projects_query = """
        MATCH (p1:Person)-[:WORKED_ON]->(proj1:Project)
        MATCH (p2:Person)-[:WORKED_ON]->(proj2:Project)
        WHERE p1.name <> p2.name
        AND NOT (p1)-[:WORKED_WITH]-(p2)
        AND (
            proj1.name = proj2.name OR
            (proj1.normalized_name IS NOT NULL AND proj2.normalized_name IS NOT NULL AND proj1.normalized_name = proj2.normalized_name)
        )
        RETURN p1, p2, proj1.name as project
        """
        similar_projects_results = graph.run(similar_projects_query).data()
        
        for result in similar_projects_results:
            p1 = result['p1']
            p2 = result['p2']
            project = result['project']
            worked_with = Relationship(p1, "WORKED_WITH", p2, project=project)
            graph.create(worked_with)
            print(f"Connected {p1['name']} and {p2['name']} who worked on similar projects: {project}")
        
        # Connect people who share skills (using fuzzy matching)
        # First, merge skills that are very similar
        merge_similar_skills_query = """
        MATCH (s1:Skill)
        MATCH (s2:Skill)
        WHERE id(s1) < id(s2)  // Avoid duplicate comparisons
        AND s1.normalized_name IS NOT NULL
        AND s2.normalized_name IS NOT NULL
        AND s1.normalized_name = s2.normalized_name
        RETURN s1, s2
        """
        
        similar_skills_results = graph.run(merge_similar_skills_query).data()
        
        # Merge similar skills by redirecting relationships
        for result in similar_skills_results:
            s1 = result['s1']
            s2 = result['s2']
            
            # Redirect all relationships from s2 to s1
            redirect_relationships_query = """
            MATCH (p:Person)-[r:HAS_SKILL]->(s2:Skill {name: $skill2_name})
            WHERE NOT (p)-[:HAS_SKILL]->(:Skill {name: $skill1_name})
            MERGE (p)-[:HAS_SKILL]->(:Skill {name: $skill1_name})
            DELETE r
            """
            graph.run(redirect_relationships_query, skill1_name=s1['name'], skill2_name=s2['name'])
            
            # Now connect people who share skills
            shared_skills_query = """
            MATCH (p1:Person)-[:HAS_SKILL]->(s:Skill)<-[:HAS_SKILL]-(p2:Person)
            WHERE p1.name <> p2.name
            WITH p1, p2, collect(s.name) as commonSkills, count(s) as skillCount
            WHERE skillCount >= 3
            AND NOT (p1)-[:SHARES_SKILLS]-(p2)
            RETURN p1, p2, commonSkills
            """
            shared_skills_results = graph.run(shared_skills_query).data()
            
            for result in shared_skills_results:
                p1 = result['p1']
                p2 = result['p2']
                common_skills = result['commonSkills']
                shares_skills = Relationship(p1, "SHARES_SKILLS", p2, 
                                         skills=common_skills, 
                                         count=len(common_skills))
                graph.create(shares_skills)
                print(f"Connected {p1['name']} and {p2['name']} who share {len(common_skills)} skills")
        
        return True
    
    except Exception as e:
        print(f"Error creating person connections: {e}")
        return False

