import os
import time
import asyncio
from collections import deque
import requests
import urllib.parse
from flask import Flask, request, jsonify, abort
from flask_cors import CORS

# Telegram API details
api_id = 27938879
api_hash = "REDACTED"

# Initialize global variables
processed_links_last_30_minutes = deque()
processed_links_today = 0
daily_reset_timestamp = time.time()

# Constants
ONE_DAY = 24 * 60 * 60
THIRTY_MINUTES = 30 * 60
MAX_LINKS_30_MINUTES = 10
MAX_LINKS_PER_DAY = 50

# Flask API for link resolution
app = Flask(__name__)

# Add more comprehensive CORS configuration
cors_config = {
    'origins': [
        'http://localhost:3000',  # React development server
        'https://play.nanoshare.in',  # Actual production domain
        'http://play.nanoshare.in',  # HTTP version of domain
        'http://127.0.0.1:3000',  # Alternative localhost
        '*'  # Wildcard for development (remove in production)
    ],
    'methods': ['GET', 'OPTIONS'],
    'allow_headers': [
        'Content-Type', 
        'Authorization', 
        'Access-Control-Allow-Credentials'
    ]
}

# Apply CORS with more granular configuration
CORS(app, 
     resources={r"/*": cors_config},
     supports_credentials=True  # Allow credentials if needed
)

def resolve_link(link):
    """
    Attempt to resolve and validate the given link.
    
    Args:
        link (str): The original link to resolve
    
    Returns:
        str: A resolved, safe URL or the original link
    """
    try:
        # Decode the link in case it's URL encoded
        decoded_link = urllib.parse.unquote(link)
        
        # Add some basic validation
        if not decoded_link.startswith(('http://', 'https://')):
            return link
        
        # Follow redirects and get the final URL
        response = requests.head(
            decoded_link, 
            allow_redirects=True, 
            timeout=5,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        
        # Return the final URL after redirects
        return response.url
    
    except requests.exceptions.RequestException as e:
        # If resolution fails, return original link
        print(f"Link resolution error: {e}")
        return link

@app.route('/', methods=['GET'])
def resolve_video_link():
    """
    Endpoint to resolve video links.
    
    Query Parameters:
        link (str): The video link to resolve
    
    Returns:
        JSON response with resolved link
    """
    link = request.args.get('link')
    
    if not link:
        abort(400, description="No link provided")
    
    try:
        resolved_link = resolve_link(link)
        return jsonify({
            "response": resolved_link,
            "original_link": link
        })
    
    except Exception as e:
        return jsonify({
            "error": str(e),
            "original_link": link
        }), 500

@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": str(error)}), 400

@app.errorhandler(500)
def server_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Use environment variable for port, default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
