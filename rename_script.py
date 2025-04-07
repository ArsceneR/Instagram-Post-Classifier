import os

# Print the current working directory
current_directory = os.getcwd()
print(f"Current Directory: {current_directory}")

# Initialize directory count
directory_count = 0

# Collect all folders and sort them by numeric suffix if present
folders = []
for root, dirs, files in os.walk(current_directory):
    if "DownloadedPosts" in root  and "-" in root:
        folders.append(root)



# Sort folders by numeric suffix, defaulting to 0 if no numeric suffix is found
sorted_folders = sorted(folders, key=lambda x: int(x.split("-")[-1]) if "-" in x and x.split("-")[-1].isdigit() else 0)

# Iterate through sorted folders and print them
for i in range (len(sorted_folders)): # iterate in reverse order to print the most recent folders first:
    post_num = sorted_folders[i].split("-")[-1] 
    os.rename(sorted_folders[i],f"Post-{post_num}") # rename the folder to a standard format
    directory_count += 1


# Print the total number of directories
print(f"Total directories = {directory_count}")


