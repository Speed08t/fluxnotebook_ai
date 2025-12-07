from flask import Flask, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/')
def serve_index():
    return send_from_directory('.', 'frontend.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

if __name__ == '__main__':
    print("Starting simple Flask server for whiteboard collaboration...")
    print("AI features disabled in this version")
    app.run(debug=True, host='0.0.0.0', port=5002)
