import json
import os
import re

from flask import Flask, jsonify, request

UPLOAD_DIR = "/tmp/file-channel"
AUTH_TOKEN = os.environ["FILE_CHANNEL_TOKEN"]
FILENAME_RE = re.compile(r"^[a-z0-9_.-]+$")

os.makedirs(UPLOAD_DIR, exist_ok=True)
app = Flask(__name__)


@app.route("/upload", methods=["POST"])
def upload():
    token = request.headers.get("token")
    filename = request.headers.get("filename")

    if token != AUTH_TOKEN:
        return "Unauthorized", 401
    if not filename or not FILENAME_RE.match(filename):
        return "Invalid filename", 400

    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(request.data)
    return "OK", 200


@app.route("/files", methods=["GET"])
def list_files():
    files_data = {}
    for fname in os.listdir(UPLOAD_DIR):
        fpath = os.path.join(UPLOAD_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            try:
                files_data[fname] = json.loads(content)
            except json.JSONDecodeError:
                files_data[fname] = None
        except Exception:
            files_data[fname] = None
    return jsonify(files_data)
