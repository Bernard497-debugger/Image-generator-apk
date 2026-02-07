import os
from flask import Flask, request, send_file, render_template_string, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import zipfile
import re

app = Flask(__name__)

# ===== SECURITY CONFIG =====
CORS(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["10 per minute"])
ACCESS_KEY = os.getenv("")  # set this in environment variables
WIDTH, HEIGHT = 800, 600
MAX_IMAGES = 10
# ============================

# === HTML FRONTEND ===
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Image Generator</title>
    <style>
        body { font-family: sans-serif; text-align: center; margin-top: 50px; background: #f2f2f2; }
        input, button { padding: 10px; font-size: 16px; margin: 5px; border-radius: 8px; border: 1px solid #333; }
        button { background: #333; color: white; cursor: pointer; transition: 0.3s; }
        button:hover { background: #555; }
        img { margin-top: 20px; max-width: 90%; height: auto; border: 3px solid #333; border-radius: 8px; box-shadow: 0px 4px 8px rgba(0,0,0,0.2); }
        #footer { margin-top: 40px; font-size: 14px; color: #555; }
    </style>
</head>
<body>
    <h1>Theme-Based Image Generator</h1>
    <input type="text" id="theme" placeholder="Enter a theme" required>
    <button onclick="generate()">Generate One Image</button>
    <button onclick="generateMultiple()">Generate Multiple Images</button>

    <div id="output">
        <img id="result" src="" alt="">
    </div>

    <div id="footer">Powered by Unsplash + Flask Server</div>

    <script>
        async function generate() {
            const theme = document.getElementById('theme').value.trim();
            if (!theme) return alert("Please enter a theme");
            document.getElementById('result').src = "";

            const response = await fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ theme })
            });

            if (!response.ok) {
                const err = await response.json();
                alert("Error: " + err.error);
                return;
            }

            const blob = await response.blob();
            const imgUrl = URL.createObjectURL(blob);
            document.getElementById('result').src = imgUrl;
        }

        async function generateMultiple() {
            const theme = document.getElementById('theme').value.trim();
            if (!theme) return alert("Please enter a theme");

            const count = prompt("How many images to generate? (max 10)", "3");
            if (!count) return;

            const response = await fetch('/generate-multiple', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ theme, count })
            });

            if (!response.ok) {
                const err = await response.json();
                alert("Error: " + err.error);
                return;
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${theme}_images.zip`;
            a.click();
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

# ===== API ROUTES =====
@app.route('/generate', methods=['POST'])
@limiter.limit("10 per minute")
def generate_image():
    data = request.get_json()
    theme = sanitize_theme(data.get('theme', 'nature'))

    try:
        return create_image(theme)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-multiple', methods=['POST'])
@limiter.limit("5 per minute")
def generate_multiple():
    data = request.get_json()
    theme = sanitize_theme(data.get('theme', 'nature'))
    try:
        count = int(data.get('count', 3))
    except ValueError:
        return jsonify({'error': 'Invalid count value'}), 400

    count = min(max(count, 1), MAX_IMAGES)

    zip_io = BytesIO()
    with zipfile.ZipFile(zip_io, 'w') as zf:
        for i in range(count):
            try:
                img_bytes = generate_image_bytes(theme)
                zf.writestr(f"{theme}_{i+1}.png", img_bytes.read())
            except Exception:
                continue

    zip_io.seek(0)
    return send_file(zip_io, mimetype='application/zip', as_attachment=True, download_name=f'{theme}_images.zip')

# ===== IMAGE GENERATION =====
def sanitize_theme(theme):
    """Remove unsafe characters and limit length"""
    safe = re.sub(r'[^a-zA-Z0-9 _-]', '', theme)
    return safe[:50] or "default"

def create_image(theme):
    img_bytes = generate_image_bytes(theme)
    img_bytes.seek(0)
    return send_file(img_bytes, mimetype='image/png')

def generate_image_bytes(theme):
    if not ACCESS_KEY:
        raise ValueError("Unsplash API key missing. Set UNSPLASH_KEY environment variable.")

    url = f'https://api.unsplash.com/photos/random?query={theme}&client_id={ACCESS_KEY}&count=1'
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, list) or not data:
        raise ValueError("No image found for that theme")

    img_url = data[0]['urls']['regular']
    img_response = requests.get(img_url, timeout=10)
    img_response.raise_for_status()

    img = Image.open(BytesIO(img_response.content)).convert("RGB")
    img = img.resize((WIDTH, HEIGHT))

    draw = ImageDraw.Draw(img)
    text = f"Theme: {theme.capitalize()}"
    font_size = 36
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    x = (WIDTH - (bbox[2] - bbox[0])) / 2
    y = HEIGHT - (bbox[3] - bbox[1]) - 20
    draw.text((x, y), text, font=font, fill="white")

    img_bytes = BytesIO()
    img.save(img_bytes, "PNG")
    img_bytes.seek(0)
    return img_bytes

# ===== RUN SERVER =====
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)