import os

start_point = 2415 
end_point = 3297 # this is the last post in the original list of posts to rename 


# Collect all folders and sort them by numeric suffix if present
folders = []
for root, dirs, files in os.walk(os.getcwd()): # os.walk will traverse the directory tree
    if "DownloadedPosts" in root  and "-" in root:
        post_num = int ( root.split("Post-")[-1] if "Post-" in root else None)
        if post_num is not None and start_point <= post_num <= end_point:
            folders.append(root)

print (f"folders found in the directory: {folders}")

folders.sort(key=lambda x: int(x.split("Post-") [-1 ] if "Post-" in x else 0)) # Sort folders by numeric suffix, defaulting to 0 if no numeric suffix is found
print("Folders containing downloaded posts:")
for folder in folders: # iterate in reverse order to print the most recent folders first:
    post_num = int( folder.split("Post-")[-1] if "Post-" in folder else None)
    print(f"Processing folder: {folder} with new post  number: {post_num-start_point+1}")
    os.rename(folder, f"Post-{ (post_num-start_point+1) }") # rename the folder to a standard format
    
