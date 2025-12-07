from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sock import Sock
import google.generativeai as genai
import os
import base64
import io
import matplotlib
matplotlib.use('Agg') # Use Agg backend for non-interactive plotting
import matplotlib.pyplot as plt
import traceback
import socket
import time
import requests
import sys
import subprocess
import tempfile
import contextlib
from io import StringIO
import asyncio
try:
    from PIL import Image
except ImportError:
    print("PIL (Pillow) not found. Installing...")
    import subprocess
    subprocess.check_call(["pip", "install", "Pillow"])
    from PIL import Image

app = Flask(__name__)
CORS(app) # Enable CORS for all routes
sock = Sock(app)

# Collaboration server (WebSocket) shared-state manager
try:
    from collaboration_server import handle_websocket as collab_handle_websocket
except Exception as e:
    collab_handle_websocket = None
    print(f"⚠️ Unable to import collaboration server handler: {e}")

# Network connectivity and DNS resolution helpers for mobile hotspot compatibility
def check_internet_connectivity():
    """Check if we can reach Google's servers, with fallback DNS resolution"""
    test_hosts = [
        ('8.8.8.8', 53),  # Google DNS
        ('1.1.1.1', 53),  # Cloudflare DNS
        ('208.67.222.222', 53),  # OpenDNS
    ]

    for host, port in test_hosts:
        try:
            socket.create_connection((host, port), timeout=5)
            return True
        except (socket.timeout, socket.error):
            continue
    return False

def resolve_google_api_host():
    """Try to resolve Google API hostname with fallback methods"""
    hostname = 'generativelanguage.googleapis.com'

    # Try standard resolution first
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror:
        pass

    # Try with different DNS servers for mobile hotspots
    dns_servers = ['8.8.8.8', '1.1.1.1', '208.67.222.222']

    for dns in dns_servers:
        try:
            # Use requests with custom DNS (simplified approach)
            response = requests.get(f'https://{hostname}', timeout=10)
            return True
        except:
            continue

    return False

def configure_genai_with_retry(api_key, max_retries=3):
    """Configure Google Generative AI with retry logic for mobile hotspots"""
    for attempt in range(max_retries):
        try:
            genai.configure(api_key=api_key)
            # Test the configuration with a simple call
            test_model = genai.GenerativeModel("gemini-2.5-flash")
            return test_model
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print("Retrying in 2 seconds...")
                time.sleep(2)
            else:
                raise e

def mask_key(api_key: str) -> str:
    """Return a lightly masked key for logging."""
    if not api_key or len(api_key) < 8:
        return "unset"
    return f"{api_key[:4]}…{api_key[-4:]}"

# Prefer env vars for the API key; fall back to the bundled demo key.
API_KEY = (
    os.environ.get("GEMINI_API_KEY")
    or os.environ.get("API_KEY")
    or "AIzaSyBdH-Gig7TYSJvT8eGpi8dDtGMGtoY1tTE"
)
MODEL_NAME = "gemini-2.5-flash"
generative_model = None

if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("API_KEY")):
    print("⚠️ No GEMINI_API_KEY/API_KEY env var found. Using the bundled demo key which is shared and likely rate-limited. Set your own key via env vars or the UI.")

PRIMARY_LATEX_INSTRUCTION = (
    "CRITICAL FORMATTING AND SOLVING RULES:\n"
    "1. MATH SOLVING: If this is a math problem, SOLVE IT STEP BY STEP with actual calculations. "
    "Show your work clearly with numbered steps and provide the final numerical answer. "
    "Don't just explain concepts - actually compute the solution.\n"
    "2. LATEX FORMATTING: For ALL mathematical expressions, equations, variables, formulas, "
    "and symbols in your response, you MUST use LaTeX formatting. "
    "Use `$$...$$` for display mathematics (equations on their own line, centered). "
    "Use `$...$` for inline mathematics (math within a sentence). "
    "For example, write `$x^2$` instead of x^2, and `$$\\frac{a}{b}$$` instead of a/b on its own line. "
    "Ensure your entire response, including all explanations and step-by-step solutions, adheres to this rule strictly. "
    "Do not use HTML tags like <sup> for math.\n"
    "3. For integrals, derivatives, equations: show the complete solution process with calculations.\n"
    "4. For word problems: set up equations and solve them numerically."
    "5.Even if the image is blank , no need to tell that again in the output , just start of with the explanation if somethiing is asked to explain or solve"
)

try:
    print("Checking network connectivity...")
    if not check_internet_connectivity():
        print("⚠️ Warning: Limited internet connectivity detected (possibly mobile hotspot)")

    print("Checking Google API accessibility...")
    if not resolve_google_api_host():
        print("⚠️ Warning: Google API host resolution issues detected")

    print("Initializing Gemini model with retry logic...")
    print(f"Using API key: {mask_key(API_KEY)}")
    generative_model = configure_genai_with_retry(API_KEY)
    print(f"✅ Successfully initialized Gemini model: {MODEL_NAME}")
except Exception as e:
    print(f"❌ Error initializing Gemini model ({MODEL_NAME}): {e}")
    print("This is likely due to network connectivity issues with mobile hotspots.")
    print("Try switching to a different network or using a VPN.")
    # Consider how to handle this - app might not be fully functional
    # For now, it will print the error and continue, endpoints will fail if model is None.

@app.route('/')
def serve_index():
    return send_from_directory('.', 'frontend.html')

@app.route('/dist/<path:filename>')
def serve_dist(filename):
    return send_from_directory('dist', filename)

@app.route('/interpret', methods=['POST'])
def interpret_image_or_text():
    data = request.json
    user_prompt = data.get('prompt', "Please analyze the provided content and image (if any).")
    # image_data_base64 should now be a string (the base64 part only) or None
    image_data_base64 = data.get('image_data')
    custom_api_key = data.get('customApiKey', None)
    selected_model = data.get('model', MODEL_NAME)
    print(f"Interpret request | prompt_len={len(user_prompt) if user_prompt else 0} | image={bool(image_data_base64)} | custom_key={bool(custom_api_key)} | model={selected_model}")

    # Configure model based on custom settings
    current_model = generative_model
    if custom_api_key:
        try:
            genai.configure(api_key=custom_api_key)
            current_model = genai.GenerativeModel(selected_model)
            print(f"Using custom API key {mask_key(custom_api_key)} with model: {selected_model}")
        except Exception as e:
            print(f"Error with custom API key: {e}")
            return jsonify({"error": "Invalid API key provided"}), 400
    elif selected_model != MODEL_NAME:
        try:
            current_model = genai.GenerativeModel(selected_model)
            print(f"Using default API key {mask_key(API_KEY)} with model: {selected_model}")
        except Exception as e:
            print(f"Error with model selection: {e}")
            return jsonify({"error": "Invalid model selected"}), 400

    if not current_model:
        return jsonify({"error": "Gemini model not initialized. Check server logs."}), 500

    final_prompt_to_ai = f"{PRIMARY_LATEX_INSTRUCTION}\n\nUser question/request: {user_prompt}"
    
    ai_response_text = ""
    python_code_suggestion = None

    try:
        content_parts = []
        content_parts.append(final_prompt_to_ai) 

        if image_data_base64:
            # This check is still good for robustness, but type should be str now
            if not isinstance(image_data_base64, str): 
                print(f"Error: image_data_base64 received was not a string, it was: {type(image_data_base64)}")
                # This indicates an issue with frontend still, or unexpected data
                return jsonify({"error": "Internal server error: Image data format incorrect on server."}), 500
            
            try:
                image_bytes = base64.b64decode(image_data_base64)
                image_part = {"mime_type": "image/png", "data": image_bytes}
                content_parts.append(image_part)
            except base64.binascii.Error as b64_error:
                print(f"Base64 decoding error: {b64_error}")
                return jsonify({"error": f"Invalid Base64 image data: {b64_error}"}), 400
            
        # Generate content
        response = current_model.generate_content(content_parts, stream=False)
        response.resolve() # Ensure all parts are resolved if stream=False was not enough
        
        raw_text_from_ai = ""
        # Extract text from response
        if response.parts:
            raw_text_from_ai = "".join(part.text for part in response.parts if hasattr(part, 'text') and part.text is not None)
        elif hasattr(response, 'text') and response.text is not None:
            raw_text_from_ai = response.text
        
        if not raw_text_from_ai: # Check if AI returned any text
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                ai_response_text = f"Content blocked by AI: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}"
            elif hasattr(response, 'candidates') and response.candidates and response.candidates[0].finish_reason != 'STOP':
                ai_response_text = f"AI finished with reason: {response.candidates[0].finish_reason}. No text content."
            else:
                ai_response_text = "AI returned no textual content or the content might have been blocked."
        else:
            ai_response_text = raw_text_from_ai

        # **** CORRECTED PYTHON CODE EXTRACTION ****
        # Attempt to extract python code block
        py_code_marker = "```python"
        code_parts = ai_response_text.split(py_code_marker)
        
        if len(code_parts) > 1:
            text_before_code = code_parts
            # The rest of the string after the first ```python
            code_and_after_text = code_parts[1] 
            
            # Split out the code block itself (ends with ```)
            end_code_marker = "```"
            code_block_parts = code_and_after_text.split(end_code_marker, 1)
            
            if len(code_block_parts) > 0:
                python_code_suggestion = code_block_parts[0].strip() # This is the code
            
            text_after_code = ""
            if len(code_block_parts) > 1:
                text_after_code = code_block_parts[1] # Text after the code block
            
            # Reconstruct ai_response_text without the code block
            ai_response_text = (text_before_code + text_after_code).strip()
        # If no "```python" block, python_code_suggestion remains None
        
        return jsonify({
            "text": ai_response_text,
            "python_code": python_code_suggestion
        })

    except Exception as e:
        error_str = str(e)
        error_message = f"AI API Error: {error_str}"

        # Check for mobile hotspot / DNS specific issues
        if "DNS resolution failed" in error_str or "generativelanguage.googleapis.com" in error_str:
            error_message = (
                "Network connectivity issue detected. This commonly happens with mobile hotspots. "
                "Try: 1) Switch to WiFi, 2) Use a VPN, 3) Change DNS settings to 8.8.8.8, "
                "or 4) Restart your mobile hotspot connection."
            )
        elif "Timeout" in error_str or "timeout" in error_str:
            error_message = (
                "Request timeout - likely due to slow mobile hotspot connection. "
                "Try moving closer to your phone or switching to a faster network."
            )
        elif "503" in error_str or "502" in error_str:
            error_message = (
                "Service temporarily unavailable. This can happen with mobile hotspots. "
                "Please try again in a few moments or switch to a different network."
            )
        # More specific error for base64 issues if not caught earlier
        elif isinstance(e, base64.binascii.Error): # Should be caught above, but as a fallback
            error_message = f"AI API Error: Invalid Base64 image data. {error_str}"
        elif hasattr(e, 'message') and e.message: # Some Google API errors have a .message attribute
            error_message = f"AI API Error: {e.message}"

        print(f"Error during Gemini API call: {traceback.format_exc()}")
        return jsonify({"error": error_message}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    try:
        data = request.json
        message = data.get('message', '')
        image_data = data.get('image_data', None)
        custom_api_key = data.get('customApiKey', None)
        selected_model = data.get('model', MODEL_NAME)
        print(f"Chat request | len(message)={len(message)} | image={bool(image_data)} | custom_key={bool(custom_api_key)} | model={selected_model}")

        if not message and not image_data:
            return jsonify({'error': 'No message or image provided'}), 400

        # Configure model based on custom settings
        current_model = generative_model
        if custom_api_key:
            try:
                genai.configure(api_key=custom_api_key)
                current_model = genai.GenerativeModel(selected_model)
                print(f"Chat: Using custom API key {mask_key(custom_api_key)} with model: {selected_model}")
            except Exception as e:
                print(f"Chat: Error with custom API key: {e}")
                return jsonify({"error": "Invalid API key provided"}), 400
        elif selected_model != MODEL_NAME:
            try:
                current_model = genai.GenerativeModel(selected_model)
                print(f"Chat: Using default API key {mask_key(API_KEY)} with model: {selected_model}")
            except Exception as e:
                print(f"Chat: Error with model selection: {e}")
                return jsonify({"error": "Invalid model selected"}), 400

        if not current_model:
            return jsonify({"error": "Gemini model not initialized"}), 500

        content_parts = []
        content_parts.append(message)

        if image_data:
            try:
                # Decode base64 image
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))

                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')

                content_parts.append(image)
                print(f"Chat: Image processed: {image.size}, mode: {image.mode}")
            except Exception as img_error:
                print(f"Chat: Image processing error: {img_error}")
                return jsonify({'error': f'Failed to process image: {str(img_error)}'}), 400

        # Generate response
        response = current_model.generate_content(content_parts)

        return jsonify({
            'response': response.text,
            'status': 'success'
        })

    except Exception as e:
        error_str = str(e)
        print(f"Chat API error: {e}")

        # Provide helpful error messages for mobile hotspot issues
        if "DNS resolution failed" in error_str or "generativelanguage.googleapis.com" in error_str:
            error_message = (
                "Network connectivity issue detected. This commonly happens with mobile hotspots. "
                "Try: 1) Switch to WiFi, 2) Use a VPN, 3) Change DNS settings to 8.8.8.8, "
                "or 4) Restart your mobile hotspot connection."
            )
        elif "Timeout" in error_str or "timeout" in error_str:
            error_message = (
                "Request timeout - likely due to slow mobile hotspot connection. "
                "Try moving closer to your phone or switching to a faster network."
            )
        elif "503" in error_str or "502" in error_str:
            error_message = (
                "Service temporarily unavailable. This can happen with mobile hotspots. "
                "Please try again in a few moments or switch to a different network."
            )
        else:
            error_message = f'Failed to generate response: {error_str}'

        return jsonify({
            'error': error_message,
            'status': 'error'
        }), 500

@app.route('/api/network-diagnostic', methods=['GET'])
def network_diagnostic():
    """Diagnostic endpoint to help troubleshoot mobile hotspot connectivity issues"""
    try:
        results = {
            'timestamp': time.time(),
            'internet_connectivity': False,
            'google_api_accessible': False,
            'dns_resolution': False,
            'recommendations': []
        }

        # Test basic internet connectivity
        results['internet_connectivity'] = check_internet_connectivity()
        if not results['internet_connectivity']:
            results['recommendations'].append("No internet connectivity detected. Check your mobile hotspot connection.")

        # Test Google API accessibility
        results['google_api_accessible'] = resolve_google_api_host()
        if not results['google_api_accessible']:
            results['recommendations'].append("Cannot reach Google AI API. Try using a VPN or changing DNS settings.")

        # Test DNS resolution
        try:
            socket.gethostbyname('google.com')
            results['dns_resolution'] = True
        except:
            results['dns_resolution'] = False
            results['recommendations'].append("DNS resolution issues detected. Try changing DNS to 8.8.8.8 or 1.1.1.1")

        # Add mobile hotspot specific recommendations
        if not results['google_api_accessible'] or not results['dns_resolution']:
            results['recommendations'].extend([
                "Mobile hotspot detected issues. Try:",
                "1. Move closer to your phone",
                "2. Restart the mobile hotspot",
                "3. Switch to WiFi if available",
                "4. Use a VPN service",
                "5. Change DNS settings on your device"
            ])

        return jsonify(results)

    except Exception as e:
        return jsonify({
            'error': f'Diagnostic failed: {str(e)}',
            'recommendations': ['Unable to run diagnostics. Check your network connection.']
        }), 500

@app.route('/execute_python', methods=['POST'])
def execute_python():
    data = request.json
    code = data.get('code')

    if not code:
        return jsonify({"error": "No code provided"}), 400

    # Restricted environment for exec
    # Add more safe builtins or modules as needed (e.g., math, numpy if installed)
    # Be very cautious with what you allow here.
    exec_globals = {
        'plt': plt,
        '__builtins__': {
            'print': print, 'range': range, 'len': len, 'Exception': Exception, 
            'list': list, 'dict': dict, 'str': str, 'int': int, 'float': float, 
            'True': True, 'False': False, 'None': None, 'abs': abs, 'round':round, 
            'sum':sum, 'min':min, 'max':max, 'pow':pow, 'enumerate':enumerate, 
            'zip':zip, 'sorted':sorted, 'map':map, 'filter':filter
            # Consider adding 'math' module if commonly used by AI and safe.
        }
    }
    local_vars = {} # To capture any variables defined by the exec'd code if needed
    
    # Capture stdout to send back to client if needed (more complex)
    # For now, relying on matplotlib plots as primary visual output

    try:
        # Execute the code
        exec(code, exec_globals, local_vars)
        
        image_base64 = None
        # Check if matplotlib was used to create a figure
        if plt.get_fignums(): # Check if there are any active figures
            fig = plt.gcf() # Get current figure
            if fig.axes: # Check if the figure actually has content (axes)
                buf = io.BytesIO()
                plt.savefig(buf, format='png', bbox_inches='tight')
                plt.close(fig) # Close the figure to free memory
                buf.seek(0)
                image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            else:
                plt.close(fig) # Close empty figure
        
        if image_base64:
            return jsonify({"output_type": "image", "data": image_base64})
        else:
            # If no image, perhaps there was text output (not captured by default)
            # Or the code ran successfully without producing a plottable output.
            return jsonify({"output_type": "text", "data": "Code executed. No visual output generated or captured."})

    except Exception as e:
        print(f"Error executing Python code: {traceback.format_exc()}")
        # Ensure all figures are closed on error too
        for fignum in plt.get_fignums():
            plt.close(plt.figure(fignum))
        return jsonify({"error": f"Python Execution Error: {str(e)}"}), 500
    finally:
        # Ensure all matplotlib figures are closed to prevent memory leaks
        plt.close('all')

# WebSocket endpoint for same-origin collaboration on platforms with a single exposed port (e.g., Railway)
if collab_handle_websocket:
    class SockWebSocketAdapter:
        """Adapter to make flask-sock websockets behave like websockets.WebSocketServerProtocol"""
        def __init__(self, ws):
            self.ws = ws

        def __aiter__(self):
            return self

        async def __anext__(self):
            # flask-sock is synchronous; offload to thread to avoid blocking the event loop
            data = await asyncio.to_thread(self.ws.receive)
            if data is None:
                raise StopAsyncIteration
            return data

        async def recv(self):
            return await self.__anext__()

        async def send(self, data: str):
            await asyncio.to_thread(self.ws.send, data)

    @sock.route('/ws')
    def websocket_endpoint(ws):
        adapter = SockWebSocketAdapter(ws)
        try:
            # Run the async handler in a fresh event loop for this connection
            asyncio.run(collab_handle_websocket(adapter, path="/ws"))
        except Exception as e:
            print(f"WebSocket handler error: {e}")


if __name__ == '__main__':
    if not generative_model:
        print("\nWARNING: Gemini model failed to initialize. AI features will not work.\n")
    port = int(os.environ.get("PORT", 5002))
    app.run(debug=False, host='0.0.0.0', port=port)
