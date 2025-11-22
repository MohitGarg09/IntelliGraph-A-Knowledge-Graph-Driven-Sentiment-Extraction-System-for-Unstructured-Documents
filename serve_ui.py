#!/usr/bin/env python3
"""
Simple HTTP server to serve the Resume Analysis System UI
Run this script to serve the web interface locally
"""

import http.server
import socketserver
import webbrowser
import os
import sys
from pathlib import Path

# Configuration
PORT = 3000
HOST = 'localhost'

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler to serve index.html for root requests"""
    
    def end_headers(self):
        # Add CORS headers for development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()
    
    def do_GET(self):
        # Serve index.html for root requests
        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()

def main():
    """Start the development server"""
    
    # Change to the directory containing the UI files
    ui_dir = Path(__file__).parent
    os.chdir(ui_dir)
    
    # Check if required files exist
    required_files = ['index.html', 'styles.css', 'script.js']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Missing required files: {', '.join(missing_files)}")
        print("Please ensure all UI files are in the current directory.")
        sys.exit(1)
    
    try:
        # Create and start the server
        with socketserver.TCPServer((HOST, PORT), CustomHTTPRequestHandler) as httpd:
            server_url = f"http://{HOST}:{PORT}"
            
            print("🚀 Resume Analysis System UI Server")
            print("=" * 50)
            print(f"📍 Server running at: {server_url}")
            print(f"📁 Serving files from: {ui_dir}")
            print("=" * 50)
            print("\n📋 Quick Setup Checklist:")
            print("  ✅ UI Server running")
            print("  🔄 Start FastAPI backend: python fastapi_app.py")
            print("  🔄 Ensure Neo4j is running on port 7687")
            print("  🔄 Set GOOGLE_API_KEY in .env file")
            print("\n💡 Tips:")
            print("  • The UI will automatically connect to http://localhost:8000")
            print("  • Check the Status tab to verify all systems are healthy")
            print("  • Use Ctrl+C to stop this server")
            print("\n🌐 Opening browser...")
            
            # Open browser automatically
            webbrowser.open(server_url)
            
            print(f"\n🎯 Ready! Access the UI at {server_url}")
            print("Press Ctrl+C to stop the server")
            
            # Start serving
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped. Goodbye!")
        sys.exit(0)
    except OSError as e:
        if e.errno == 98:  # Address already in use
            print(f"❌ Port {PORT} is already in use.")
            print("Either:")
            print(f"  1. Stop the process using port {PORT}")
            print(f"  2. Change PORT in this script to a different number")
        else:
            print(f"❌ Error starting server: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
