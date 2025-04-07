import os

#this is the content of the first post. it is repeated in .txt files whenever the post is downloaded 
#this helps us find the duplication point in the downloaded posts.
target_content = (
    """Did you know that the DEA collected 3 TONS (599,897 lbs) of prescription drugs during the October 2023 Take Back Day?? Prepare for the next one on April 27, 2024 by learning more about how improper disposal of medication affects us all! https://ow.ly/nouV50RcCUn

#HEARTSforFamilies #UnderageDrinkingandDrugPrevention #DBHDD #saveouryouth #parenting #opioidprevention #teens #youthawareness #drugaddiction #alcoholaddiction #support #mentalillness #hope #giveyourselfachance #drugprevention #STEPup #fentanylawareness #beatdepression #community #narcotics #anxiety #drugabuse #addictionrecovery #STEPupWare #STEPupJenkins #STEPupColquitt #STEPupBacon #BaconCountyPIP #STEPupGrady #SWGASuicidePrevention
"""
)

# Get the current working directory
current_directory = os.getcwd()

post_directories = []  # This will store the post numbers where the target content is found


for root,dirs, files in os.walk(current_directory):
    if os.path.basename(root).__contains__("Post-"):
        for file in files:
            if file.endswith(".txt"):
                file_path = os.path.join(root, file)
                try:
                    # Open and read the file
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        # Check if the target content is in the file
                        if target_content in content:
                            print(f"Match found in: {file_path}")
                            post_num = file_path.split("2024")[-2].split("Post-")[-1]  # Extract the post number from the file path
                            post_directories.append(int(post_num.removesuffix('/')))  # Store the post number without trailing slash
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")

post_directories.sort()

#find post with largest adjacent difference to identify the best start point that allows as many posts to be kept as possible
max_diff = float('-inf') # Initialize max_diff to negative infinity
for i in range(1, len(post_directories)):
    # Calculate the difference between adjacent post numbers
    diff = post_directories[i] - post_directories[i - 1] 
    if diff > max_diff:
        print(f"Gap found between Post-{post_directories[i-1]} and Post-{post_directories[i]}. Using Post-{post_directories[i-1]} as the last point to rename.")
        max_diff = diff
        
start_point = post_directories[-1]
end_point = -1 # this is the last post in the original list of posts to rename 

