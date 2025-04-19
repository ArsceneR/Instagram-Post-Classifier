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
)

app = modal.App(image=image)

@app.function() #register function within app 
def retrieve_and_classify()->None: 
    pass  

@app.local_entrypoint()
def classify()->None:
    pass
     