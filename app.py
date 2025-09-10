from flask import Flask, render_template, request
import requests
import json
import base64
from io import BytesIO
from PIL import Image
from datetime import datetime

app = Flask(__name__)

# ── Azure ML endpoint + storage (replace as needed) ─────────────────────────────
azure_ml_endpoint = "https://nc-edp-sand-aml01-mdfull.northeurope.inference.ml.azure.com/score"
api_key = "FNtftxXtqGbPkqiHivV43RQmaEykzOurszM4wPpVSywzAh2DYWgXJQQJ99BIAAAAAAAAAAAAINFRAZML1k8O"

# Base URL already includes the container
sas_base_url = "https://ncedpdevstor001.blob.core.windows.net/ncedpdevds01"
# Adjust this path to match where your blobs live
blob_image_prefix = "/landing/SAP/IMAGES/MATERIALS/ALL_MATERIALS_RAW/MATERIALS/"
sas_token = "sp=r&st=2025-09-10T08:03:54Z&se=2030-03-21T16:18:54Z&sv=2024-11-04&sr=c&sig=6DHkwQ7DPuhWGfXuRMktALxG9F0UDM6GFjBVSdfHaP8%3D"

# ── Health check for Azure ─────────────────────────────────────────────────────
@app.get("/healthz")
def healthz():
    return {"status": "ok"}, 200


@app.route("/", methods=["GET", "POST"])
def index():
    items = []
    top_n = "10"
    filename = ""

    if request.method == "POST":
        uploaded_file = request.files.get("file")
        top_n = request.form.get("top_n", "10")

        if uploaded_file:
            filename = uploaded_file.filename

            # Convert uploaded image → base64 (JPEG)
            image = Image.open(uploaded_file.stream).convert("RGB")
            buffered = BytesIO()
            image.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

            # Ensure top_n is an int
            try:
                top_n_int = int(top_n)
            except (TypeError, ValueError):
                top_n_int = 10

            # Image-only payload for your endpoint
            payload = {
                "image": img_str,
                "top_n": top_n_int
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            # Call Azure ML endpoint
            response = requests.post(azure_ml_endpoint, headers=headers, json=payload)
            print("API Response Status Code:", response.status_code)
            print("API Response Text:", response.text)

            if response.status_code == 200:
                try:
                    api_response = response.json()
                    if isinstance(api_response, string_types := (str,)):
                        api_response = json.loads(api_response)

                    # Expect: list of {"Filename", "MaterialCode", "similarity"}
                    if isinstance(api_response, list) and all(isinstance(item, dict) for item in api_response):
                        for item in api_response:
                            fname = item.get("Filename")
                            if fname:
                                item["image_url"] = f"{sas_base_url}{blob_image_prefix}{fname}?{sas_token}"
                        items = api_response
                    else:
                        print("Unexpected response format. Expected a list of dicts.")
                except json.JSONDecodeError as e:
                    print("Failed to decode JSON:", e)
            else:
                print("API request failed with status code:", response.status_code)

    return render_template(
        "index.html",
        items=items,
        top_n=top_n,
        filename=filename,
        current_year=datetime.now().year
    )

@app.route("/about")
def about():
    return render_template("about.html", current_year=datetime.now().year)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
