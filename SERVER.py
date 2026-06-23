import os
import json
import requests
from flask import Flask, request, jsonify
from functools import wraps
import tempfile
import zipfile
from datetime import datetime
import shutil

app = Flask(__name__)

API_TOKEN        = os.environ.get("API_TOKEN", "change-me-secret")
DISCORD_WEBHOOK  = os.environ.get("DISCORD_WEBHOOK_URL", "")
MAX_FILE_SIZE    = 25 * 1024 * 1024  # 25 MB


def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        
        if not token:
            token = request.args.get("token", "")
        
        if token != API_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Discord Webhook Server is running 🚀"})


@app.route("/send", methods=["POST"])
@require_token
def send_to_discord():
    if not DISCORD_WEBHOOK:
        return jsonify({"error": "DISCORD_WEBHOOK_URL not configured"}), 500

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    discord_payload = smart_payload_builder(data)

    resp = requests.post(DISCORD_WEBHOOK, json=discord_payload, timeout=10)

    if resp.status_code in (200, 204):
        return jsonify({"success": True, "message": "Sent to Discord ✅"}), 200
    else:
        return jsonify({
            "error": "Discord rejected the request",
            "status": resp.status_code,
            "detail": resp.text
        }), 502


@app.route("/send/embed", methods=["POST"])
@require_token
def send_embed():
    if not DISCORD_WEBHOOK:
        return jsonify({"error": "DISCORD_WEBHOOK_URL not configured"}), 500

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    discord_payload = smart_embed_builder(data)

    resp = requests.post(DISCORD_WEBHOOK, json=discord_payload, timeout=10)

    if resp.status_code in (200, 204):
        return jsonify({"success": True, "message": "Embed sent to Discord ✅"}), 200
    else:
        return jsonify({
            "error": "Discord rejected the request",
            "status": resp.status_code,
            "detail": resp.text
        }), 502


@app.route("/send/file", methods=["POST"])
@require_token
def send_file_to_discord():
    if not DISCORD_WEBHOOK:
        return jsonify({"error": "DISCORD_WEBHOOK_URL not configured"}), 500

    try:
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}")
            file.save(temp_file.name)
            temp_file.close()
            
            success = send_file_to_discord_webhook(temp_file.name, file.filename)
            os.unlink(temp_file.name)
            
            if success:
                return jsonify({"success": True, "message": f"File {file.filename} sent ✅"}), 200
            else:
                return jsonify({"error": "Failed to send file"}), 502
        
        data = request.get_json(silent=True)
        if data and 'folder_path' in data:
            folder_path = data.get('folder_path')
            zip_name = data.get('zip_name', 'archive')
            category_name = data.get('category_name', 'Files')
            
            if not os.path.exists(folder_path):
                return jsonify({"error": f"Folder {folder_path} does not exist"}), 400
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_path = os.path.join(tempfile.gettempdir(), f"{zip_name}_{timestamp}.zip")
            
            success = create_zip(folder_path, zip_path)
            if not success:
                return jsonify({"error": "Failed to create ZIP"}), 500
            
            file_size = os.path.getsize(zip_path)
            if file_size > MAX_FILE_SIZE:
                os.unlink(zip_path)
                return jsonify({"error": f"File too large ({file_size} bytes). Max is 25MB"}), 400
            
            send_success = send_file_to_discord_webhook(
                zip_path, 
                os.path.basename(zip_path),
                caption=f"📦 {category_name} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            os.unlink(zip_path)
            
            if send_success:
                return jsonify({"success": True, "message": f"ZIP {zip_name} sent ✅", "size": file_size}), 200
            else:
                return jsonify({"error": "Failed to send ZIP"}), 502
        
        return jsonify({"error": "No file provided"}), 400
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/send/files", methods=["POST"])
@require_token
def send_multiple_files():
    if not DISCORD_WEBHOOK:
        return jsonify({"error": "DISCORD_WEBHOOK_URL not configured"}), 500
    
    if 'files' not in request.files:
        return jsonify({"error": "No files provided"}), 400
    
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({"error": "No files selected"}), 400
    
    uploaded = []
    failed = []
    
    for file in files:
        if file.filename == '':
            continue
        
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}")
            file.save(temp_file.name)
            temp_file.close()
            
            success = send_file_to_discord_webhook(temp_file.name, file.filename)
            os.unlink(temp_file.name)
            
            if success:
                uploaded.append(file.filename)
            else:
                failed.append(file.filename)
                
        except Exception as e:
            failed.append(f"{file.filename} (error: {str(e)})")
    
    return jsonify({
        "success": True,
        "uploaded": uploaded,
        "failed": failed,
        "total": len(uploaded) + len(failed)
    }), 200



def smart_payload_builder(data):

    if "content" in data or "embeds" in data:
        return data
    
    if "text" in data or "message" in data:
        return {"content": data.get("text") or data.get("message")}
    
    if "title" in data or "fields" in data:
        embed = {
            "title": data.get("title", "Notification"),
            "description": data.get("description", ""),
            "color": data.get("color", 5814783),
            "fields": data.get("fields", [])
        }
        if "footer" in data:
            embed["footer"] = {"text": data["footer"]}
        return {"embeds": [embed]}
    
    if "embeds" in data:
        return data
    
    pretty = json.dumps(data, ensure_ascii=False, indent=2)
    return {"content": f"```json\n{pretty}\n```"}


def smart_embed_builder(data):

    if "embeds" in data:
        return data
    
    if "title" in data or "fields" in data:
        embed = {
            "title": data.get("title", "Notification"),
            "description": data.get("description", ""),
            "color": data.get("color", 5814783),
            "fields": data.get("fields", [])
        }
        if "footer" in data:
            embed["footer"] = {"text": data["footer"]}
        if "timestamp" in data:
            embed["timestamp"] = data["timestamp"]
        
        return {
            "username": data.get("username", "Webhook Bot"),
            "embeds": [embed]
        }
    
    if "content" in data:
        return {"content": data["content"]}
    
    pretty = json.dumps(data, ensure_ascii=False, indent=2)
    embed = {
        "title": "Received Data",
        "description": f"```json\n{pretty}\n```",
        "color": 5814783
    }
    return {"embeds": [embed]}


def send_file_to_discord_webhook(file_path: str, filename: str, caption: str = None):
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f, 'application/octet-stream')}
            data = {
                'username': 'ZIP Bot',
                'avatar_url': 'https://cdn.discordapp.com/embed/avatars/1.png'
            }
            if caption:
                data['content'] = caption
            
            response = requests.post(DISCORD_WEBHOOK, files=files, data=data, timeout=30)
            return response.status_code in (200, 204)
            
    except Exception as e:
        print(f"Error sending file: {str(e)}")
        return False


def create_zip(source_folder: str, zip_path: str) -> bool:
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(source_folder):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, source_folder)
                    zf.write(full_path, arcname)
        return True
    except Exception as e:
        print(f"Error creating ZIP: {str(e)}")
        return False


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
