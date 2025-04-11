import os
import json
from modules.data_reader import get_column_data


def findFailed(file_paths) -> None:
    """Find and log failed URLs."""
    urls_from_excel = get_column_data(file_paths)   
    
    for root,_,files in os.wallk(os.path.expanduser("~/Downloads/All_Downloads")):
        if "Post" in root:
            for file in files:
                file_path = os.path.join(root,file)
                if file.endswith(".xz"):
                    os.system(f"unxz {file_path}")
                    uncompressed_file = file_path.replace(".xz", "")
                    with open(uncompressed_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        shortcode = data["node"]["shortcode"]
                        url = f"https://www.instagram.com/p/{shortcode}/"
                        if url in urls_from_excel:
                            urls_from_excel.remove(url) 
                        else:
                            with open("failed_urls.txt", "a", encoding="utf-8") as file:
                                file.write(url + "\n")
                    os.remove(uncompressed_file)
    
    print(f"number of failed urls: {len(urls_from_excel)}")
    
    
    #also write the remaining urls to a file for retry purposes 
    with open("failed_urls.txt", "a", encoding="utf-8") as file:
        for url in urls_from_excel:
            file.write(url + "\n")

        




