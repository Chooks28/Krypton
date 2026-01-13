from flask import Flask, render_template, request, jsonify, send_from_directory
import subprocess
import os
import pathlib

app = Flask(__name__, static_folder="static", template_folder="templates")
ROOT = pathlib.Path(__file__).resolve().parent.parent

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run_step():
    data = request.get_json()
    step = data.get("step")
    try:
        if step == "static":
            result = subprocess.run(["php", "StaticRouteExtractor.php"], cwd=ROOT, capture_output=True, text=True)
        elif step == "merge_openapi":
            result = subprocess.run(["python3", "merge_openapi.py"], cwd=ROOT, capture_output=True, text=True)
        elif step == "record_har":
            result = subprocess.run(["python3", "record_wp_har.py"], cwd=ROOT, capture_output=True, text=True)
        elif step == "extract_har":
            result = subprocess.run(["python3", "extract_full_rest_from_har.py"], cwd=ROOT, capture_output=True, text=True)
        elif step == "super_merge":
            result = subprocess.run(["python3", "super_merge_openapi.py"], cwd=ROOT, capture_output=True, text=True)
        else:
            return jsonify(success=False, error="Unknown step"), 400

        return jsonify(success=result.returncode == 0, output=result.stdout, error=result.stderr)
    except Exception as e:
        return jsonify(success=False, error=str(e))

@app.route("/download/<path:filename>")
def download(filename):
    # Allow downloading from multiple directories
    if filename in ["static_routes_full.json", "static_routes_full_1.json"]:
        return send_from_directory(ROOT / "output", filename)
    elif filename == "merged_openapi.yaml":
        return send_from_directory(ROOT / "output", filename)
    elif filename == "full_har_openapi.yaml" or filename == "full_har_endpoints.json":
        return send_from_directory(ROOT / "captures", filename)
    elif filename == "merged_spec_smart.yaml":
        return send_from_directory(ROOT, filename)
    else:
        return "File not found", 404

if __name__ == "__main__":
    app.run(debug=True)
