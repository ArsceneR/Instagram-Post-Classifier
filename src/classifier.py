import os
from pathlib import Path
import json
import time
import logging
import modal


try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded environment variables from .env file.")
except ImportError:
    print("python-dotenv not installed, skipping .env file loading.")




#initialize secrets 
_default_local_downloads = Path.home() / "Downloads" / "All_Downloads"
LOCAL_DOWNLOADS_DIR = Path(os.environ.get("LOCAL_DOWNLOADS_DIR", str(_default_local_downloads)))

CONTAINER_DOWNLOADS_DIR = Path(os.environ.get("CONTAINER_DOWNLOADS_DIR", "/Downloads/"))

SECRET_NAME = os.environ.get("MODAL_SECRET_NAME", "google_drive_secret")

ROOT_FOLDER_NAME = os.environ.get("GDRIVE_ROOT_FOLDER_NAME", "Classified_Posts")

GPU_CONFIG = os.environ.get("MODAL_GPU_CONFIG", "L40S")

PYTHON_VERSION = os.environ.get("MODAL_PYTHON_VERSION", "3.10")

GDRIVE_PARENT_FOLDER_ID = os.environ.get("GDRIVE_PARENT_FOLDER_ID")

# --- Logging Setup ---
log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)
# Basic config for local execution, Modal might override format in containers
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Use a named logger


if not GDRIVE_PARENT_FOLDER_ID:
    if modal.is_local(): #we've gotta set this up locally
        logger.info("Running locally, GDRIVE_PARENT_FOLDER_ID is not required.")
        raise ValueError("GDRIVE_PARENT_FOLDER_ID environment variable is not set. Halting execution. Please init the environment file")


# --- Modal Image Definition ---
# Defines the container environment
image = (
    modal.Image.debian_slim(python_version=PYTHON_VERSION)
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
        "python-dotenv", # Needed for .env loading if used inside container (less common)
    )
    .add_local_dir(str(LOCAL_DOWNLOADS_DIR), str(CONTAINER_DOWNLOADS_DIR))
)

# Create a Modal App instance
app = modal.App(f"clip-classifier-{ROOT_FOLDER_NAME.lower().replace(' ', '-')}", image=image)



def create_drive_folder(service, folder_name, parent_folder_id=None):
    """Creates a new folder in Google Drive or returns its ID if it already exists."""
    from googleapiclient.errors import HttpError

    # Escape single quotes in folder names for the query
    safe_folder_name = folder_name.replace("'", "\\'")

    query = (
        f"mimeType = 'application/vnd.google-apps.folder' "
        f"and name = '{safe_folder_name}' "
        f"and trashed = false"
    )
    if parent_folder_id:
        query += f" and '{parent_folder_id}' in parents"
    else:
        # If checking in root (no parent specified), ensure it's directly in 'root'
        query += " and 'root' in parents"

    try:
        response = service.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
        folders = response.get('files', [])
        if folders:
            folder_id = folders[0]['id']
            logger.debug(f"Folder '{folder_name}' already exists with ID: {folder_id} under parent {parent_folder_id or 'root'}")
            return (False, folder_id)
    except HttpError as error:
        logger.error(f"An error occurred checking for folder '{folder_name}': {error}")
        return None # Indicate failure

    # Folder does not exist, create it
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_folder_id:
        file_metadata['parents'] = [parent_folder_id]

    try:
        file = service.files().create(body=file_metadata, fields='id').execute()
        folder_id = file.get('id')
        logger.info(f"Created folder '{folder_name}' with ID: {folder_id} under parent {parent_folder_id or 'root'}")
        return (True, folder_id)
    except HttpError as error:
        logger.error(f"An error occurred creating folder '{folder_name}': {error}")
        return None # Indicate failure


def upload_to_drive(service, folder_id, file_path):
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    import mimetypes # Use standard library for mime types

    file_name = file_path.name
    # Guess mime type using standard library, provide default
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        # Handle special cases or provide a default
        if file_name.endswith(".json.xz"):
            mime_type = "application/x-xz"
        else:
            mime_type = "application/octet-stream" # Generic binary

    file_metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

    try:
        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )
        logger.info(f"Uploaded '{file_name}' to folder ID '{folder_id}', file ID '{file.get('id')}'")
        return True
    except Exception as e:
        logger.error(f"An error occurred while uploading '{file_name}': {e}")
        return False 

@app.cls(
    gpu=GPU_CONFIG,
    secrets=[modal.Secret.from_name(SECRET_NAME), modal.Secret.from_dotenv()],
    timeout=1800, # 30 minutes timeout per container
    # max_containers=10, 
    # min_containers=2
    
)
class Classifier:
        
    @modal.enter()
    def start(self): 
        
        self.classification_folder_id = os.environ.get("CLASSIFICATION_FOLDER_ID")
        if not self.classification_folder_id:
            raise ValueError("CLASSIFICATION_FOLDER_ID environment variable not set in container. Cannot proceed.")
        logger.info(f"Using classification folder ID: {self.classification_folder_id}")
        
        self.category_folders = { "opioid_related": os.environ.get("OPIOID_RELATED_FOLDER_ID"),
                                 "neutral_content": os.environ.get("NEUTRAL_CONTENT_FOLDER_ID"),
                                 "error":os.environ.get("ERROR_FOLDER_ID") }
        if not self.category_folders:
            raise ValueError("Category folder IDs not set in environment. Cannot proceed.")
        
        self.CATEGORIES = {
            "opioid_related": [
                "heroin injection",
                "fentanyl pills",
                "oxycodone pills",
                "opioid overdose",
                "drugs",
                "prescription opioid abuse",
                "illegal opioid sales", 
                "opioid manufacturing",
                "counterfeit pills",
                "opioid crisis",
                "IV drug use",
                "black tar heroin",
                "opioid addiction",
                "opioid withdrawal",
                "needle exchange",
                "opioid death",
                "naloxone administration",
                "opioid street price",
                "opioid trafficking",
                "pill press",
                "substance-induced fatality",
                "prescription medication",
                "pharmaceutical pills",
                "drug paraphernalia",
                "pill bottles",
                "medicine capsules",
                "syringes",
                "drug injection",
                "controlled substance",
                "painkillers",
                "analgesics",
                "medication storage",
                "prescription refills",
                "pharmacy",
                "doctor's prescription",
                "medicine cabinet",
                "first aid kit",
                "addiction recovery",
                "rehabilitation center",
                "sobriety support",
                "harm reduction",
                "safe injection",
                "overdose prevention",
                "drug education",
                "addiction treatment",
                "recovery meeting",
                "12 step program",
                "relapse prevention",
                "drug testing",
                "clean needle program",
                "naloxone kit",
                "medication-assisted treatment",
                "sober living",
                "counseling for addiction",
                "support groups",
                "detoxification",
                "intervention",
                "pill"  
            ],

            "neutral_content": [
                "a natural landscape",
                "food and drink",
                "people socializing",
                "pets and animals",
                "daily activities",
                "travel photo",
                "sports and recreation",
                "technology",
                "art and creativity",
                "fashion and style",
                "vehicles and transportation",
                "home decoration",
                "office environment",
                "a cooking recipe",
                "fitness exercise",
                "a news event",
                "political discussion",
                "educational material",
                "a motivational quote",
                "family gathering",
                "holiday celebration",
                "nature photography",
                "architecture photo",
                "abstract art", 
                "advertisement",
                "promotional material",
            ]
        }

        # Generate prompts and map them back to categories *once*
        self.ALL_PROMPTS = []
        self.PROMPT_TO_CATEGORY_MAP = []
        for category, prompts_list in self.CATEGORIES.items():
            formatted_prompts = [f"a photo of {prompt}" for prompt in prompts_list]
            self.ALL_PROMPTS.extend(formatted_prompts)
            self.PROMPT_TO_CATEGORY_MAP.extend([category] * len(prompts_list))

      
        logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__) # Use instance logger
        self.logger.info(f"Initializing container on Python {PYTHON_VERSION} with GPU {GPU_CONFIG}...")

        import torch
        import clip
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        # Load CLIP model
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.logger.info(f"Using device: {self.device}")
        try:

            self.model, self.preprocess = clip.load("ViT-B/32", device=self.device) 
            self.logger.info("CLIP model ViT-B/32 loaded.")
        except Exception as e:
            self.logger.exception("Failed to load CLIP model!")
            raise  # Critical error, stop container initialization

        # Pre-tokenize and encode text prompts
        try:
            with torch.no_grad():
                text_inputs = clip.tokenize(self.ALL_PROMPTS).to(self.device)
                self.text_features = self.model.encode_text(text_inputs)
                # Normalize text features once for efficient comparison later
                self.text_features /= self.text_features.norm(dim=-1, keepdim=True)
            self.logger.info(f"Encoded {len(self.ALL_PROMPTS)} text prompts.")
        except Exception as e:
             self.logger.exception("Failed to encode text prompts!")
             raise # Critical error

        # Build Google Drive API client using service account from mounted secret
        try:
            service_account_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])
            creds = service_account.Credentials.from_service_account_info(
                service_account_info, scopes=["https://www.googleapis.com/auth/drive.file"] # Scope for creating files/folders
            )
            self.drive_service = build("drive", "v3", credentials=creds)
            self.logger.info("Google Drive service client built successfully.")
        except KeyError:
            self.logger.error(f"SECRET ERROR: 'SERVICE_ACCOUNT_JSON' not found in environment. Ensure Modal secret '{SECRET_NAME}' is populated correctly.")
            raise # Critical error, cannot proceed without Drive access
        except Exception as e:
            self.logger.exception("Failed to build Google Drive service client!")
            raise # Critical error


    def _analyze_image(self, image_path: Path):
        """Analyzes a single image using the pre-loaded model and prompts."""
        import torch
        from PIL import Image, UnidentifiedImageError

        analyze_start_time = time.time()
        try:
            # Open and preprocess the image
            image = Image.open(image_path).convert('RGB')
            image_input = self.preprocess(image).unsqueeze(0).to(self.device)

            with torch.no_grad():
                # Encode image and normalize features
                image_features = self.model.encode_image(image_input)
                image_features /= image_features.norm(dim=-1, keepdim=True)

                # Calculate similarities with pre-computed, normalized text features
                # (100.0 * image_features @ self.text_features.T) gives logits
                # softmax converts logits to probabilities
                similarities = (100.0 * image_features @ self.text_features.T).softmax(dim=-1)
                scores = similarities.cpu().numpy()[0] # Get scores array for the single image

            # Aggregate scores per category
            category_scores = {cat_name: 0.0 for cat_name in self.CATEGORIES.keys()}
            for i, score in enumerate(scores):
                category = self.PROMPT_TO_CATEGORY_MAP[i]
                if category in category_scores: # Ensure mapping is correct
                     category_scores[category] += score # Sum probabilities for prompts in the same category

            # Determine best category based on highest summed probability
            if not category_scores: # Should not happen if CATEGORIES is populated
                 best_category = "error"
                 self.logger.error(f"No category scores generated for {image_path.name}")
            else:
                 best_category = max(category_scores, key=category_scores.get)

            duration = time.time() - analyze_start_time
            self.logger.debug(f"Image {image_path.name} classified as: {best_category} in {duration:.2f}s. (Scores: { {k: f'{v:.3f}' for k, v in category_scores.items()} })")
            return best_category

        except UnidentifiedImageError:
            self.logger.error(f"Cannot identify image file (corrupted or wrong format): {image_path}")
            return "error"
        except FileNotFoundError:
             self.logger.error(f"Image file not found at path: {image_path}")
             return "error"
        except Exception as e:
            self.logger.exception(f"Unexpected error during image analysis for {image_path}: {e}")
            return "error"

    @modal.method()
    def process_item(self, item_dir_name: str):
        """
        Processes a single item directory: finds image, classifies, uploads all files.
        Designed to be called via .map().

        Args:
            item_dir_name: The name of the subdirectory within CONTAINER_DOWNLOADS_DIR to process.

        Returns:
            A dictionary summarizing the processing result for this item.
        """
        if not self.drive_service:
             msg = f"Skipping item '{item_dir_name}' due to missing Google Drive service in container."
             self.logger.error(msg)
             return {"item": item_dir_name, "status": "error", "reason": msg}
        if not self.category_folders:
             msg = f"Skipping item '{item_dir_name}' due to missing category folder configuration."
             self.logger.error(msg)
             return {"item": item_dir_name, "status": "error", "reason": msg}


        item_start_time = time.time()
        item_path = CONTAINER_DOWNLOADS_DIR / item_dir_name
        self.logger.info(f"Processing item directory: {item_path}")

        image_path = None
        files_to_upload = []
        category = "error" # Default category if issues arise early
        target_category_folder_id = self.category_folders.get("error") # Default GDrive target

        if not item_path.is_dir():
            msg = f"Item path is not a directory: {item_path}. Skipping."
            self.logger.warning(msg)
            return {"item": item_dir_name, "status": "skipped", "reason": msg}

        # Find the first image file and collect all files for upload
        try:
            for file in item_path.iterdir():
                if file.is_file():
                    files_to_upload.append(file)
                    # Find the first image based on common extensions (case-insensitive)
                    if file.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp", ".bmp"] and image_path is None:
                        image_path = file
                        self.logger.debug(f"Found image file: {file.name}")
            if not files_to_upload:
                self.logger.warning(f"No files found in directory: {item_path}")
                # Decide if this is an error or just skippable
                return {"item": item_dir_name, "status": "skipped", "reason": "No files in directory"}

        except Exception as e:
            self.logger.exception(f"Error scanning files in {item_path}: {e}")
            # Treat as error, attempt upload to error folder
            category = "error"
            target_category_folder_id = self.category_folders.get("error")
            return
        else:
            if not image_path:
                self.logger.warning(f"No image file found in {item_path}. Classifying item as 'error'.")
                category = "error"
            else:
                # Analyze the found image
                category = self._analyze_image(image_path) # Returns 'error' on failure

            # Get the Google Drive folder ID for the determined category
            target_category_folder_id = self.category_folders.get(category)
            if not target_category_folder_id:
                self.logger.error(f"CRITICAL: No GDrive folder ID configured for category '{category}'. Uploading to error folder ID {self.category_folders.get('error')} instead.")
                target_category_folder_id = self.category_folders.get("error") # Fallback to error folder
                # If even the error folder ID is missing (checked in __enter__), we have a bigger problem
                if not target_category_folder_id:
                    msg = f"Cannot upload '{item_dir_name}', target category '{category}' AND error folder IDs are missing."
                    self.logger.critical(msg)
                    return {"item": item_dir_name, "status": "error", "reason": msg}
                
      

        # Create the specific subfolder for this item within the category folder
        # Use item_dir_name(shortcode) as the subfolder name in Google Drive
        new_folder , destination_subfolder_id = create_drive_folder(self.drive_service, item_dir_name, target_category_folder_id)
      
        if not new_folder:
            existing_folder_id = destination_subfolder_id
            self.logger.info(f"Item folder '{item_dir_name}' already exists in category '{category}' (ID: {existing_folder_id}). Skipping upload.")
            item_duration = time.time() - item_start_time # Include classification time if done above
            return {
                "item": item_dir_name,
                "status": "skipped_exist", # New status
                "category": category,
                "reason": "Subfolder already exists in Google Drive",
                "duration_seconds": round(item_duration, 2)
             }
   
        #fatal error 
        if not destination_subfolder_id:
            self.logger.error(f"Failed to create or find destination subfolder '{item_dir_name}' in category folder ID {target_category_folder_id}. Attempting upload to category folder root.")
            return 
            

        # Upload all collected files to the determined destination folder
        upload_count = 0
        upload_errors = 0
        if files_to_upload:
             self.logger.info(f"Uploading {len(files_to_upload)} files for '{item_dir_name}' to Drive folder ID {destination_subfolder_id} (Category: {category})")
             # Potential optimization: Use a ThreadPoolExecutor here for concurrent uploads if I/O bound
             # from concurrent.futures import ThreadPoolExecutor
             # def upload_task(file_p):
             #      return upload_to_drive(self.drive_service, destination_subfolder_id, file_p)
             # with ThreadPoolExecutor(max_workers=5) as executor: # Adjust worker count
             #      results = list(executor.map(upload_task, files_to_upload))
             # upload_count = sum(1 for r in results if r is not None)
             # upload_errors = len(results) - upload_count

             # Simple sequential upload:
             for file_path in files_to_upload:
                 file_id = upload_to_drive(self.drive_service, destination_subfolder_id, file_path)
                 if file_id:
                      upload_count += 1
                 else:
                      upload_errors += 1
                      self.logger.warning(f"Failed to upload file: {file_path.name}")

             self.logger.info(f"Finished uploading for '{item_dir_name}'. Success: {upload_count}, Errors: {upload_errors}")
    
        item_duration = time.time() - item_start_time
        final_status = "processed" if upload_errors == 0 else "processed_with_errors"
        if upload_count == 0 and upload_errors > 0:
             final_status = "error" # Treat as error if nothing could be uploaded


        return {
            "item": item_dir_name,
            "status": final_status,
            "category": category,
            "files_found": len(files_to_upload),
            "uploads_successful": upload_count,
            "upload_errors": upload_errors,
            "duration_seconds": round(item_duration, 2)
        }
#(Run Once locally)
# Ensures the main GDrive folder exists before starting parallel processing.

@app.function(secrets=[modal.Secret.from_name(SECRET_NAME)])
def setup_drive_folders(req_parent_folder_id: str = None):
    """
    Creates the main classification folder in Google Drive if it doesn't exist.
    Returns the ID of this main classification folder.

    Args:
        req_parent_folder_id: Explicit GDrive folder ID to create the root folder under.
                              If None, uses GDRIVE_PARENT_FOLDER_ID env var or defaults to 'My Drive'.
    """
    # Configure logging for this function if needed
    setup_logger = logging.getLogger("setup_drive")
    setup_logger.setLevel(log_level) # Use global log level

    import json
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    parent_folder_id_to_use = req_parent_folder_id if req_parent_folder_id else GDRIVE_PARENT_FOLDER_ID
    setup_logger.info(f"Running setup. Target root folder name: '{ROOT_FOLDER_NAME}'. Parent ID: {parent_folder_id_to_use or 'My Drive root'}")

    # Build service client just for this setup task
    try:
        with open(os.environ.get("SERVICE_ACCOUNT_JSON_PATH")) as f:
            service_account_info = json.load(f)
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=["https://www.googleapis.com/auth/drive.file"]
        )
        service = build("drive", "v3", credentials=creds)
        setup_logger.info("Google Drive service client built for setup.")
    except KeyError:
         setup_logger.error(f"SECRET ERROR: 'SERVICE_ACCOUNT_JSON' not found in environment for setup function. Ensure Modal secret '{SECRET_NAME}' is correct.")
         raise
    except Exception as e:
         setup_logger.exception("Failed to build Google Drive service client during setup.")
         raise

    # Create or get the main classification folder using the configured name and parent
    storage_folder_id = create_drive_folder(service, ROOT_FOLDER_NAME, parent_folder_id_to_use)[1]

    if not storage_folder_id:
        setup_logger.critical(f"Failed to create or find the main storage folder '{ROOT_FOLDER_NAME}' under parent '{parent_folder_id_to_use or 'root'}'. Cannot proceed.")
        raise RuntimeError(f"Could not establish root Google Drive folder: {ROOT_FOLDER_NAME}")

    setup_logger.info(f"Setup complete. Main classification folder ('{ROOT_FOLDER_NAME}') ID: {storage_folder_id}")
    
    parent_classification_folder_id = storage_folder_id

    # Define consistent names for Drive folders based on categories
    CATEGORY_DRIVE_NAMES = {
        "opioid_related": "Opioid Related",
        "neutral_content": "Neutral Content",
        "error": "Processing Errors" # Folder for items that fail processing
    }

    category_folders = {}
    logger.info(f"Ensuring category folders exist under parent folder ID: {parent_classification_folder_id}")
    for category_key, drive_folder_name in CATEGORY_DRIVE_NAMES.items():
        new_folder, folder_id = create_drive_folder(service, drive_folder_name, parent_classification_folder_id)
        if folder_id and new_folder :
            category_folders[category_key] = folder_id
            with open(".env", "a") as f:
                f.write(f"\n{category_key.upper()}_FOLDER_ID={folder_id}\n")
                
            logger.debug(f"Obtained folder ID for '{category_key}': {folder_id}")            
        else:
            # Log error but potentially continue if error folder fails? Decide policy.
            logger.error(f"Failed to get or create Drive folder for category: {category_key} (Drive name: {drive_folder_name})")
            # If the 'error' folder itself fails, it's critical
            if category_key == "error":
                return None # Cannot proceed without an error folder

    logger.info(f"Category folder IDs obtained: {category_folders}")

    
    return category_folders

# --- Main Application Entrypoint ---

@app.local_entrypoint()
def main(drive_parent_id: str = None): # Allow overriding parent ID via CLI flag e.g. --drive-parent-id "..." useful for readme and deploying
    """
    Main entry point: Sets up Drive, lists items, runs parallel classification.
    """
    run_start_time = time.time()
    # Use the explicitly passed CLI flag highest precedence, then .env var, then None
    parent_id_for_setup = drive_parent_id if drive_parent_id else GDRIVE_PARENT_FOLDER_ID

    logger.info("--- Starting Classification Job ---")
    logger.info(f"Using local downloads source: {LOCAL_DOWNLOADS_DIR}")
    logger.info(f"Target container directory: {CONTAINER_DOWNLOADS_DIR}")
    logger.info(f"Modal App Name: {app.name}")
    logger.info(f"Requested GPU: {GPU_CONFIG}")

    # 1. Run setup function locally to create classificaiton folder 
    logger.info("Step 1: Setting up Google Drive folder structure...")
    try:
        # Pass the resolved parent ID to the remote setup function
        setup_drive_folders.local(req_parent_folder_id=parent_id_for_setup)
    except Exception as e:
        logger.exception("Failed to setup Google Drive structure. Exiting.")
        return


    # 2. List items (directories) to process from the container's perspective
    logger.info(f"Step 2: Scanning for item directories in container path: {CONTAINER_DOWNLOADS_DIR}")
    items_to_process = []
    try:
        # Check if the directory exists locally first (helps catch config errors early)
        if not LOCAL_DOWNLOADS_DIR.exists():
             logger.error(f"Local directory does not exist: {LOCAL_DOWNLOADS_DIR}. Check LOCAL_DOWNLOADS_DIR in config/env.")
             return
        if not LOCAL_DOWNLOADS_DIR.is_dir():
             logger.error(f"Local path is not a directory: {LOCAL_DOWNLOADS_DIR}.")
             return

        # since the  paths inside the container will mirror this structure under CONTAINER_DOWNLOADS_DIR.
        items_to_process = [d.name for d in LOCAL_DOWNLOADS_DIR.iterdir() if d.is_dir()]
        if not items_to_process:
            logger.warning(f"No subdirectories found in {LOCAL_DOWNLOADS_DIR}. Nothing to process.")
            return
        logger.info(f"Found {len(items_to_process)} potential item directories to process.")

    except Exception as e:
        logger.exception(f"Error listing local item directories in {LOCAL_DOWNLOADS_DIR}: {e}")
        return # Cannot proceed if listing fails

    # 3. Instantiate the Classifier class and process items in parallel using .map()
    logger.info(f"Step 3: Starting parallel processing for {len(items_to_process)} items...")
    classifier = Classifier() # Pass the folder ID to the container


    
    results = []
    map_start_time = time.time()

    # Use .map for parallel execution. `return_exceptions=True` allows processing to continue if one item fails.
    for result in classifier.process_item.map(items_to_process, return_exceptions=True):
        if isinstance(result, Exception):
            # Log the exception traceback from the remote container
            logger.error(f"An exception occurred in remote processing: {result}", exc_info=False) # exc_info=False as traceback is in result
            results.append({"status": "framework_error", "error": str(result)})
        elif isinstance(result, dict):
            # Log summary from the returned dictionary
            logger.info(f"Processed '{result.get('item', 'N/A')}': Status={result.get('status', 'N/A')}, Category={result.get('category', 'N/A')}, Duration={result.get('duration_seconds', 'N/A')}s")
            results.append(result)
        else:
            # Handle unexpected return types
            logger.warning(f"Received unexpected result type from process_item.map: {type(result)}")
            results.append({"status": "unknown_result", "data": str(result)})


    map_duration = time.time() - map_start_time
    logger.info(f"Step 3 Complete. Parallel processing finished in {map_duration:.2f} seconds.")

    # 5. Summarize Results
    logger.info("--- Job Summary ---")
    processed_ok = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "processed")
    processed_w_errors = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "processed_with_errors")
    errors = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "error")
    framework_errors = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "framework_error")
    skipped = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "skipped")
    unknown = len(results) - (processed_ok + processed_w_errors + errors + framework_errors + skipped)

    logger.info(f"Total items processed: {len(results)} / {len(items_to_process)}")
    logger.info(f"  Processed successfully: {processed_ok}")
    logger.info(f"  Processed with upload errors: {processed_w_errors}")
    logger.info(f"  Skipped (e.g., not dir, no files): {skipped}")
    logger.info(f"  Processing errors (classification/scan): {errors}")
    logger.info(f"  Framework/Container errors: {framework_errors}")
    if unknown > 0: logger.warning(f"  Unknown result status: {unknown}")

    total_duration = time.time() - run_start_time
    logger.info(f"Total job duration: {total_duration:.2f} seconds.")
    logger.info("--- Classification Job Finished ---")