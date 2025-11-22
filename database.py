from py2neo import Node, Relationship, NodeMatcher, Graph
import time



# ========================
# NEO4J CONNECTOR CLASS
# ========================

class Neo4jConnector:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="123456789", max_retries=3, retry_delay=2):
        self.uri = uri
        self.user = user
        self.password = password
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.graph = None
        
    def connect(self):
        """Attempt to connect to Neo4j with retries"""
        retries = 0
        last_exception = None
        
        while retries < self.max_retries:
            try:
                print(f"Attempting to connect to Neo4j ({retries + 1}/{self.max_retries})...")
                self.graph = Graph(self.uri, auth=(self.user, self.password))
                # Test the connection
                self.graph.run("MATCH (n) RETURN count(n) LIMIT 1")
                print("Successfully connected to Neo4j!")
                return self.graph
            except Exception as e:
                last_exception = e
                retries += 1
                print(f"Connection attempt {retries} failed: {str(e)}")
                if retries < self.max_retries:
                    print(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
        
        print(f"Failed to connect to Neo4j after {self.max_retries} attempts.")
        raise ConnectionError(f"Could not connect to Neo4j: {str(last_exception)}")
