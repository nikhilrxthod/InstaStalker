from flask import Flask, render_template, Response, request, jsonify
import subprocess
import json
import os
import sys
import glob
import threading

sys.stdout.reconfigure(encoding="utf-8")

app = Flask(__name__)

CONFIG_FILE = "config.json"
BASE_DIR = "monitor_data"

current_process = None
process_lock = threading.Lock()

os.makedirs("monitor_data", exist_ok=True)
os.makedirs("data", exist_ok=True)

def stream_process(command):
    global current_process

    with process_lock:

        current_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=os.getcwd()
        )

    for line in iter(current_process.stdout.readline, ''):
        yield f"data: {line}\n\n"

    current_process.stdout.close()
    current_process.wait()

    yield "data: __END__\n\n"

    with process_lock:
        current_process = None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login")
def login():
    return Response(
        stream_process([sys.executable, "login_setup.py"]),
        mimetype="text/event-stream"
    )


@app.route("/monitor")
def monitor():
    return Response(
        stream_process([sys.executable, "instagram_monitor.py"]),
        mimetype="text/event-stream"
    )


@app.route("/stop")
def stop():

    global current_process

    with process_lock:

        if current_process:
            current_process.terminate()
            current_process = None
            return "Stopped"

    return "No process running"


@app.route("/config", methods=["GET"])
def get_config():

    with open(CONFIG_FILE, "r") as f:
        data = f.read()

    return data


@app.route("/config", methods=["POST"])
def save_config():

    new_config = request.data.decode("utf-8")

    with open(CONFIG_FILE, "w") as f:
        f.write(new_config)

    return jsonify({"status": "saved"})


@app.route("/files")
def list_files():

    files = []

    files.append("config.json")

    files += glob.glob("monitor_data/*/*.json")

    return jsonify(files)


def safe_path(path):

    abs_path = os.path.abspath(path)
    base = os.path.abspath(BASE_DIR)

    if abs_path.startswith(base) or abs_path == os.path.abspath("config.json"):
        return abs_path

    return None


@app.route("/file")
def read_file():

    path = request.args.get("path")

    safe = safe_path(path)

    if not safe:
        return "Invalid path", 400

    with open(safe, "r") as f:
        return f.read()


@app.route("/file", methods=["POST"])
def save_file():

    path = request.args.get("path")

    safe = safe_path(path)

    if not safe:
        return "Invalid path", 400

    data = request.data.decode("utf-8")

    with open(safe, "w") as f:
        f.write(data)

    return jsonify({"status": "saved"})

if __name__ == "__main__":
    app.run()