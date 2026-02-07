import os
import re
import zipfile
import requests
from io import BytesIO
from flask import Flask, request, send_file, render_template_string, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# ===== CONFIGURATION =====
CORS(app)
# Use Memory storage for Limiter to avoid needing a database like Redis on free tiers
limiter = Limiter(
    get_remote_address, 
    app=app, 
    default_limits=["20 per minute"],
    storage_uri="memory://"
)

ACCESS_KEY = os.getenv("UNSPLASH_KEY")
WIDTH, HEIGHT = 800, 600
MAX_IMAGES = 10

# === HTML FRONTEND ===
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Image Generator</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; padding: 20px; background: #f8f9fa; color: #333; }
        .container { max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        input { width: 80%; padding: 12px; font-size: 16px; margin: 10px 0; border-radius: 6px; border: 1px solid #ddd; }
        button { padding: 12px 20px; font-size: 16px; margin: 5px; border-radius: 6px; border: none; background: #007bff; color: white; cursor: pointer; transition: 0.2s; }
        button:hover { background: #0056b3; }
        button.secondary { background: #6c757d; }
        #result-container { margin-top: 25px; }
        img { max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); display: none; }
        .loading { display: none; color: #007bff; font-weight: bold; margin: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Theme Generator</h1>
        <p>Enter a keyword to pull and label images</p>
        <input type="text" id="theme" placeholder="e.g. Cyberpunk, Forest, Space" required>
        <br>
        <button onclick="generate()">Generate Image</button>
        <button class="secondary" onclick="generateMultiple()">Download ZIP (3)</button>
        
        <div id="loading" class="loading">Processing... Please wait...</div>
        <div id="result-container">
            <img id="result" src="" alt="Generated Preview">
        </div>
    </div>

    <script>
        const loading = document.getElementById('loading');
        const resultImg = document.getElementById('result');

        async function generate() {
            const theme = document.getElementById('theme').value.trim();
            if (!theme) return alert("Please enter a theme");
            
            loading.style.display = 'block';
            resultImg.style.display = 'none';

            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ theme })
                });

                if (!response.ok) throw new Error("API Limit reached or Unsplash error");

                const blob = await response.blob();
                resultImg.src = URL.createObjectURL(blob);
                resultImg.style.display = 'block';
            } catch (err) {
                alert(err.message);
            } finally {
                loading.style.display = 'none';
            }
        }

        async function generateMultiple() {
            const theme = document.getElementById('theme').value.trim();
            if (!theme) return alert("Please enter a theme");
            
            loading.style.display = 'block';

            try {
                const response = await fetch('/generate-multiple', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ theme, count: 3 })
                });

                if (!response.ok) throw new Error("Failed to generate ZIP");

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${theme}_collection.zip`;
                a.click();
            } catch (err) {
                alert(err.message);
            } finally {
                loading.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate', methods=['POST'])
def generate_route():
    data = request.get_json() or {}
    theme = sanitize_theme(data.get('theme', 'nature'))
    try:
        img_bytes = generate_image_logic(theme)
        return send_file(img_bytes, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-multiple', methods=['POST'])
def generate_multiple_route():
    data = request.get_json() or {}
    theme = sanitize_theme(data.get('theme', 'nature'))
    count = min(int(data.get('count', 3)), MAX_IMAGES)

    zip_io = BytesIO()
    with zipfile.ZipFile(zip_io, 'w') as zf:
        for i in range(count):
            try:
                img_bytes = generate_image_logic(theme)
                zf.writestr(f"{theme}_{i+1}.png", img_bytes.getvalue())
            except:
                continue

    zip_io.seek(0)
    return send_file(zip_io, mimetype='application/zip', as_attachment=True, download_name=f'{theme}.zip')

def sanitize_theme(theme):
    return re.sub(r'[^a-zA-Z0-9 ]', '', theme)[:30] or "default"

def generate_image_logic(theme):
    if not ACCESS_KEY:
        raise ValueError("Missing UNSPLASH_KEY environment variable")

    # Fetch from Unsplash
    url = f"https://api.unsplash.com/photos/random?query={theme}&client_id={ACCESS_KEY}"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    img_data = res.json()
    
    img_res = requests.get(img_data['urls']['regular'], timeout=10)
    img = Image.open(BytesIO(img_res.content)).convert("RGB")
    img = img.resize((WIDTH, HEIGHT))

    # Drawing text
    draw = ImageDraw.Draw(img)
    text = theme.upper()
    
    # Try to find a system font (works on most Linux hosts like Render)
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "arial.ttf"
    ]
    font = None
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, 40)
            break
        except:
            continue
    
    if not font:
        font = ImageFont.load_default()

    # Center text
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((WIDTH-tw)/2, HEIGHT-th-40), text, font=font, fill="white", stroke_width=2, stroke_fill="black")

    out = BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out

if __name__ == '__main__':
    # Use the port assigned by the host, or 5000 for local testing
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)