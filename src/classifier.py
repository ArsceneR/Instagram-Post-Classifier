import modal 
import json
import os 
from google.oauth2 import service_account  
from googleapiclient.discovery import build

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
        "google-auth-httplib2"
    
    ).add_local_dir("~/Downloads/All_Downloads", "/Downloads/")
)

app = modal.App(image=image)

@app.function(secrets=[modal.Secret.from_name("google_drive_secret"), modal.Secret.from_name("storage_folder")]) 
def classify_posts(storage_folder_id)->None: 
    import clip
    import torch
    import os
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    model, preprocess = clip.load("ViT-B/32", device=device)

    
    download_dir = '/Downloads/'
    count = 0
    
    '''
    #traverse the downloads remote directory 
    for root, _, files in os.walk(download_dir): 
        for file in files: 
            pass
        count+=1
    
    print(f"total directories = {count}")   
    
    '''
    

@app.function()
def setup():
    import os
    from dotenv import load_dotenv
    import json
    from google.oauth2 import service_account  
    from googleapiclient.discovery import build
    
    load_dotenv()

    service_account_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])

    # Write to a file (required by Google libraries)
    with open("service_account.json", "w") as f:
        json.dump(service_account_info, f)

    creds = service_account.Credentials.from_service_account_file(
        "service_account.json", 
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
        print(f"Folder already exists with ID: {folders[0]['id']}")
        return folders[0]['id']
    
    # Folder does not exist, create it
    create_drive_folder(service , new_folder_name, parent_id)

def create_drive_folder(folder_name, parent_folder_id=None):
    """Creates a new folder in Google Drive.

    Args:
        folder_name (str): The name of the folder to create.
        parent_folder_id (str, optional): The ID of the parent folder.
                                        Defaults to None (root of Drive).

    Returns:
        str: The ID of the newly created folder, or None if creation failed.
    """
    
    service_account_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])

    # Write to a file (required by Google libraries)
    with open("service_account.json", "w") as f:
        json.dump(service_account_info, f)

    creds = service_account.Credentials.from_service_account_file(
        "service_account.json", 
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
        print(f"Folder '{folder_name}' created with ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        print(f"An error occurred while creating folder '{folder_name}': {e}")
        return None
       
#modal app entry point
@app.local_entrypoint()
def classify()->None:
    storage_folder_id = setup.local() #create the directory in google drive.. this function is ran locally for cost purposes. 
    classify_posts.remote(storage_folder_id)
    
    