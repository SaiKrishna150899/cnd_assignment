import os
import json
import requests
from flask import Flask, redirect, request, render_template, send_from_directory, url_for, Response
from google.cloud import storage, secretmanager
import google.generativeai as genai
from google.oauth2 import service_account

app = Flask(__name__)
app.secret_key = "your-secret-key"

os.makedirs('files', exist_ok=True)

def authenticate_gcp():
    return storage.Client()

def get_gemini_api_key():
    secret_client = secretmanager.SecretManagerServiceClient()
    secret_name = "projects/cloudnative12/secrets/geminiSecret/versions/latest"
    response = secret_client.access_secret_version(request={"name": secret_name})
    gemini_api_key = response.payload.data.decode("UTF-8")
    return gemini_api_key

gemini_api_key = get_gemini_api_key()
genai.configure(api_key=gemini_api_key)

bucket_name = 'picart1'
storage_client = authenticate_gcp()

def list_images_in_bucket():
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs()

    image_metadata = []
    image_files = {}

    for blob in blobs:
        if blob.name.lower().endswith(('.jpg', '.jpeg', '.png')):
            image_name = blob.name
            description_file = image_name.rsplit('.', 1)[0] + '.txt'
            image_files[image_name] = description_file

    for image_name, description_file in image_files.items():
        desc_blob = bucket.blob(description_file)
        if not desc_blob.exists():
            continue

        try:
            description_content = desc_blob.download_as_text().splitlines()
        except Exception as e:
            print(f"Error downloading {description_file}: {e}")
            continue

        title = description_content[0] if len(description_content) > 0 else "No Title"
        description = description_content[1] if len(description_content) > 1 else "No Description"

        image_metadata.append({
            "name": image_name,
            "metadata": {
                "title": title,
                "description": description
            }
        })

    return image_metadata

@app.route('/')
def home():
    images = list_images_in_bucket()
    return render_template('index.html', images=images)

@app.route('/files/<user_id>/<filename>')
def files(user_id, filename):
    blob_path = f"{user_id}/{filename}"
    blob = storage_client.bucket(bucket_name).blob(blob_path)
    
    if not blob.exists():
        return "File not found", 404

    content = blob.download_as_bytes()
    content_type = blob.content_type or 'application/octet-stream'
    return Response(content, content_type=content_type)

def upload_to_gemini(image_path, mime_type="image/jpeg"):
    file = genai.upload_file(image_path, mime_type=mime_type)
    return file

def generate_description(image_file):
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
    }
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
    )
    chat_session = model.start_chat(
        history=[ 
            {"role": "user", "parts": ["Generate title and a description for an image\n"]},
            {"role": "model", "parts": ["Please provide me with the image you want a title and description for!"]},
            {"role": "user", "parts": [image_file, "Generate a title and a description."]},
        ]
    )
    response = chat_session.send_message("Generate a title and a description.")
    try:
        parsed_response = json.loads(response.text)
        title = parsed_response.get("title", "No Title Available")
        description = parsed_response.get("description", "No Description Available")
        return title, description
    except json.JSONDecodeError:
        return "Error generating title", "Error generating description"

def upload_blob(bucket_name, file, blob_name, user_id):
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(os.path.join(user_id, blob_name))
    blob.upload_from_file(file)

@app.route('/upload', methods=['POST'])
def upload():
    user_id = "default_user"
    user_folder = os.path.join('files', user_id)
    os.makedirs(user_folder, exist_ok=True)
    file = request.files['form_file']
    filename = file.filename
    if filename == '':
        return "No file selected", 400
    if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        return "Invalid file format. Only .jpg, .jpeg, and .png files are allowed.", 400
    local_image_path = os.path.join(user_folder, filename)
    file.save(local_image_path)
    image_file = upload_to_gemini(local_image_path)
    title, description = generate_description(image_file)
    local_text_path = os.path.join(user_folder, os.path.splitext(filename)[0] + '.txt')
    with open(local_text_path, 'w') as text_file:
        text_file.write(f"{title}\n{description}")
    with open(local_text_path, 'rb') as text_file:
        upload_blob(bucket_name, text_file, os.path.basename(local_text_path), user_id)
    file.seek(0)
    upload_blob(bucket_name, file, os.path.basename(local_image_path), user_id)
    return redirect('/')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
