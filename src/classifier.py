import modal 

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
        "git+https://github.com/openai/CLIP.git"
    )
    .add_local_dir(local_path='~/Downloads/All_Downloads/', remote_path='/Downloads/')
)

app = modal.App(image=image)

@app.function() #register function within app 
def retrieve_and_classify()->None: 
    import clip
    import torch
    import os 
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    download_dir = '/Downloads/'
    count = 0
    #traverse the downloads remote directory 
    for root, _, files in os.walk(download_dir): 
        for file in files: 
            pass
        count+=1
    
    print(f"total directories = {count}")
    

#modal app entry point
@app.local_entrypoint()
def classify()->None:
    retrieve_and_classify.remote()
     