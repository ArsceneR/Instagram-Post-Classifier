import os 

def find_files_without_metadata(download_dir: str) -> None:        
    valid_paths = []
    folders_without_metadata = []
    count = 0
    
    # Walk through the directory to find .xz files
    #make sure to change directory to your Downloads folder.
    for root, _, files in os.walk(os.path.expanduser(download_dir)): 
        if "Post" in root: #filter the directories to only include the posts.
            has_metadata = False
            for file in files:
                file_path = os.path.join(root, file)
                if file.endswith(".xz"):
                    valid_paths.append(file_path)
                    has_metadata = True
            if not has_metadata:
                folders_without_metadata.append(root)

            
        count+=1 
    
    print(f"number of directories: {count}")
    print(f"number of valid paths(i.e files with metadata): {len(valid_paths)}")
    print(f"number of folders without metadata: {len(folders_without_metadata)}")
    folders_without_metadata.sort(key=lambda x: int(x.split("-")[-1]))  
    
        
   
    