import modal 
import json
import os 
import logging
from google.oauth2 import service_account  
from googleapiclient.discovery import build
from dotenv import load_dotenv

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .pip_install(
        "torch",
        "torchvision",
        "ftfy",
        "regex",
        "tqdm",
        "Pillow",
        "git+https://github.com/openai/CLIP.git",
        "google-api-python-client",
        "google-auth-oauthlib",
        "google-auth-httplib2", 
        "pillow"
    
    ).add_local_dir("~/Downloads/All_Downloads", "/Downloads/")
)

load_dotenv()

app = modal.App(image=image)


def analyze_content(image_path, caption_path, model, preprocess, device):
    """Analyzes image and caption using CLIP."""
    categories = {
        "highly_opioid_related": [
            "heroin injection", "fentanyl pills", "oxycodone tablets",
            "opioid overdose", "drug induced coma", "prescription opioid abuse",
            "illegal opioid sales", "opioid manufacturing", "counterfeit pills",
            "opioid crisis", "IV drug use", "black tar heroin",
            "opioid addiction symptoms", "opioid withdrawal", "needle exchange",
            "opioid related death", "narcan administration", "opioid street price",
            "opioid trafficking", "pill press", "substance-induced fatality"
        ],
        "moderately_opioid_related": [
            "prescription medication", "pharmaceutical pills", "drug paraphernalia",
            "pill bottles", "medicine capsules", "syringes", "drug injection",
            "controlled substance", "painkillers", "analgesics",
            "sedatives", "tranquilizers", "sleep aids", "anti-anxiety medication",
            "medication storage", "prescription refills", "pharmacy",
            "doctor's prescription", "medicine cabinet", "first aid kit",
            "addiction recovery", "drug rehabilitation", "sobriety support",
            "harm reduction", "safe injection practices", "overdose prevention",
            "drug education", "addiction treatment", "recovery meetings",
            "12 step program", "relapse prevention", "drug testing",
            "clean needle program", "naloxone training", "medication-assisted treatment",
            "sober living", "counseling for addiction", "support groups for addiction",
            "detoxification", "intervention"
        ],
        "neutral_content": [
            "natural landscape", "food and drink", "people socializing",
            "pets and animals", "daily activities", "travel photos",
            "sports and recreation", "technology", "art and creativity",
            "fashion and style", "vehicles and transportation", "home decoration",
            "office environment", "cooking recipe", "fitness exercise",
            "news event", "political discussion", "scientific research",
            "educational material", "motivational quote", "religious sermon",
            "family gathering", "holiday celebration"
        ]
    }

    try:
        image = Image.open(image_path).convert('RGB')
        image_input = preprocess(image).unsqueeze(0).to(device)
    except Exception as e:
        logging.error(f"Image processing error: {e}")
        return "error"
    
    with torch.no_grad():
        image_features = model.encode_image(image_input)

    # Prepare text features
    # Read and process caption
    text_description = ""
    if os.path.exists(caption_path):
        try:
            with open(caption_path, "r", encoding="utf-8") as f:
                text_description = f.read().strip()
            text_description = f"Caption: {text_description}" if text_description else ""
        except Exception as e:
            logging.error(f"Caption reading error: {e}")
            text_description = ""

    # Tokenize categories and caption
    prompts = []
    prompt_categories = []
    for category, prompts_list in categories.items():
        prompts.extend([f"a photo of {prompt}" for prompt in prompts_list])
        prompt_categories.extend([category] * len(prompts_list))  # Match category to each prompt

    if text_description:
        prompts.append(text_description)  # Append full description
        prompt_categories.append("text_description")  # Mark its category as text_description

    text_inputs = clip.tokenize(prompts).to(device)

    with torch.no_grad():
        text_features = model.encode_text(text_inputs)

    # Process features and get similarity
    image_features /= image_features.norm(dim=-1, keepdim=True)
    text_features /= text_features.norm(dim=-1, keepdim=True)
    similarities = (100.0 * image_features @ text_features.T).softmax(dim=-1).cpu().numpy()[0]

    # Map similarities back to categories, accounting for each category
    category_scores = {}
    for i, cat in enumerate(prompt_categories):
        if cat not in category_scores:
            category_scores[cat] = 0.0
        category_scores[cat] += similarities[i]

    # Get best category
    best_category = max(category_scores, key=category_scores.get)

    # Log output
    logging.info(f"Image classification: {best_category}")

    return best_category

@app.function(gpu="L40S", secrets=[modal.Secret.from_name("google_drive_secret")])
def classify_posts(storage_folder_id):
    """Classifies posts and uploads to Google Drive."""
    import os
    import json
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    import torch
    import clip
    from PIL import Image

    # Setup Logging
    logging.basicConfig(level=logging.INFO)

    # Load Google Drive API credentials
    service_account_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=["https://www.googleapis.com/auth/drive"] #least permission. no read permissions necessary. 
    )
    service = build("drive", "v3", credentials=creds)

    # Load CLIP model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)

    # Define Category Folders
    category_folders = {}

    # Create Category Folders in Root Drive Folder. key = foldername, value = folder_id 
    category_folders["highly_opioid_related"] = create_drive_folder(
        service, "Highly Opioid Related", storage_folder_id
    )
    category_folders["moderately_opioid_related"] = create_drive_folder(
        service, "Moderately Opioid Related", storage_folder_id
    )
    category_folders["neutral_content"] = create_drive_folder(
        service, "Neutral Content", storage_folder_id
    )
    category_folders["error"] = create_drive_folder(service, "Processing Errors", storage_folder_id)

    # Traverse the directories
    download_dir = "/Downloads/"
    for item in os.listdir(download_dir):
        item_path = os.path.join(download_dir, item)
        # Check if it's a directory
        if os.path.isdir(item_path):
            image_path = None
            caption_path = None
            # Check the files in that directory
            for file in os.listdir(item_path):
                file_path = os.path.join(item_path, file)
                if file.lower().endswith((".jpg", ".jpeg", ".png")):
                    image_path = file_path
                elif file.lower().endswith(".txt"):
                    caption_path = file_path

            # Check if both image and caption are found
            if image_path and (caption_path or os.path.exists(caption_path)):
                try:
                    category = analyze_content(image_path, caption_path, model, preprocess, device)
                    dest_folder_id = category_folders.get(category, category_folders["error"])

                    if not dest_folder_id:
                        logging.warning(f"No folder for category: {category}. Uploading to Error")
                        dest_folder_id = category_folders["error"]

                    for file in os.listdir(item_path):
                        upload_to_drive(service, dest_folder_id, os.path.join(item_path, file))
                    logging.info(f"Uploaded '{item}' to {category}")

                except Exception as e:
                    logging.exception(f"Failed to process {item}: {e}")
                    # Upload to Error Folder
                    for file in os.listdir(item_path):
                        upload_to_drive(service, category_folders["error"], os.path.join(item_path, file))


@app.function()
def setup():
    import os
    import json
    from google.oauth2 import service_account  
    from googleapiclient.discovery import build
    

    service_account_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])

    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=[ 
            'https://www.googleapis.com/auth/drive.metadata.readonly',
            'https://www.googleapis.com/auth/drive.file'
        ]
    )
    service = build('drive', 'v3', credentials=creds)
    
    new_folder_name = 'Classified_Posts'
    parent_id = os.environ["parent_folder_id"]

    # Properly format the query string
    q = (
        f"mimeType = 'application/vnd.google-apps.folder' "
        f"and name = '{new_folder_name}' "
        f"and '{parent_id}' in parents"
    )

    response = service.files().list(q=q, fields="files(id, name)").execute()
    folders = response.get('files', [])

    if folders:
        # Folder exists, use its ID
        logging.info(f"Folder already exists with ID: {folders[0]['id']}")
        return folders[0]['id']
    
    
    # Folder does not exist, create it
    storage_folder_id = create_drive_folder(service , new_folder_name, parent_id)
    return storage_folder_id

def create_drive_folder(service, folder_name, parent_folder_id=None):
    """Creates a new folder in Google Drive.

    Args:
        folder_name (str): The name of the folder to create.
        parent_folder_id (str, optional): The ID of the parent folder.
                                        Defaults to None (root of Drive).

    Returns:
        str: The ID of the newly created folder, or None if creation failed.
    """
    if not service: 
        service_account_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])

        creds = service_account.Credentials.from_service_account_file(
            service_account_info, 
            scopes=[ 
                'https://www.googleapis.com/auth/drive.metadata.readonly',
                'https://www.googleapis.com/auth/drive.file'
            ]
        )
        service = build('drive', 'v3', credentials=creds)
    
    
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_folder_id:
        file_metadata['parents'] = [parent_folder_id]

    try:
        file = service.files().create(body=file_metadata, fields='id').execute()
        logging.info(f"Folder '{folder_name}' created with ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        logging.info(f"An error occurred while creating folder '{folder_name}': {e}")
        return None


#used only remotely, service is a param because i dont want to keep rebuilding 
def upload_to_drive(service, folder_id, file_path):
    """Uploads a file to Google Drive."""
    file_name = os.path.basename(file_path)
    mime_type = "image/jpeg" if file_name.lower().endswith((".jpg", ".jpeg")) else "text/plain"

    file_metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

    try:
        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )
        logging.info(f"Uploaded '{file_name}' to folder ID '{folder_id}', file ID '{file.get('id')}'")
    except Exception as e:
        logging.error(f"An error occurred while uploading '{file_name}': {e}")



#modal app entry point
@app.local_entrypoint()
def classify()->None:
    storage_folder_id = setup.local() #create the directory in google drive.. this function is ran locally for cost purposes.
    classify_posts.remote(storage_folder_id)
    
    