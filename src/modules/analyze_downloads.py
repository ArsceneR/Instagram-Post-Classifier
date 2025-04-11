import os
import json
import lzma
import logging
from typing import Dict, List
from modules.data_reader import get_column_data

def find_failed_urls(file_paths: List[str], download_dir: str) -> List[str]:
    """Find and log failed(not downloaded) URLs that are in Excel files but missing from downloaded posts."""
    
    # Get all URLs from the Excel files
    urls_from_excel = set(get_column_data(file_paths))
    logging.info(f"Number of unique urls: {len(urls_from_excel)}")
    
    #clear file 
    with open("failed_urls.txt", "w", encoding="utf-8") as file:
        file.truncate(0)

    # Walk through download directory
    for root, _, files in os.walk(os.path.expanduser(download_dir)):
        if "Post" in root:
            for file in files:
                if file.endswith(".xz"):
                    file_path = os.path.join(root, file)
                    try:
                        with lzma.open(file_path, "rt", encoding="utf-8") as f:
                            data = json.load(f)
                            shortcode = data.get("node", {}).get("shortcode")
                            if shortcode:
                                url = f"https://www.instagram.com/p/{shortcode}/"
                                urls_from_excel.discard(url)  # remove if exists
                    except (lzma.LZMAError, json.JSONDecodeError, OSError) as e:
                        logging.error(f"Error processing {file_path}: {e}")

    # Log the number of failed URLs
    logging.info(f"Number of failed URLs: {len(urls_from_excel)}")

    # Write failed URLs to file
    if urls_from_excel:
        with open("failed_urls.txt", "a", encoding="utf-8") as file:
            for url in urls_from_excel:
                file.write(url + "\n")

    # Log each failed URL and its index
     # Log each failed URL and its index
    for i, url in enumerate(urls_from_excel):
        logging.info(f"Failed URL: {url} at index: {i}")

    return list(urls_from_excel)

def find_empty_folders(file_paths: List[str], download_dir: str) -> None:
    """Find and log empty folders in the download directory."""
   
    empty_dirs = []
    for root, _, files in os.walk(os.path.expanduser(download_dir)): 
        if "Post" in root and len(files) == 0:
            empty_dirs.append(root)
    
    empty_dirs.sort(key=lambda x:int(x.split("-")[-1]))
    
    for directory in empty_dirs:
        with open("empty_folders.txt", "a", encoding="utf-8") as file:
            file.write(directory + "\n")
        logging.info(f"Empty folder: {directory}")


def find_duplicate_downloads(file_paths: List[str], download_dir: str) -> Dict[str, int]:
    """
    Find and log duplicate downloads by comparing Excel URLs with downloaded files.
    
    Args:
        file_paths: List of Excel file paths containing URLs
        download_dir: Directory containing downloaded posts
        
    Returns:
        Dictionary mapping URLs to their count (negative counts indicate duplicates)
    """
    urls = get_column_data(file_paths)
    url_counts = {url: 1 for url in urls}  # Initialize with count of 1 for each URL
    
    logging.info(f"Number of unique URLs from Excel: {len(url_counts)}")
    
    for root, _, files in os.walk(os.path.expanduser(download_dir)):
        if "Post" in root:
            for file in files:
                file_path = os.path.join(root, file)
                if file.endswith(".xz"):
                    try:
                        with lzma.open(file_path, "rt", encoding="utf-8") as f:
                            data = json.load(f)
                            shortcode = data["node"]["shortcode"]
                            url = f"https://www.instagram.com/p/{shortcode}/"
                            url_counts[url] = url_counts.get(url, 0) - 1  # Decrement count for each download
                            
                    except (lzma.LZMAError, json.JSONDecodeError) as e:
                        logging.error(f"Error processing {file_path}: {e}")
    
    duplicates = sum(1 for count in url_counts.values() if count < 0)
    for url, count in url_counts.items(): 
        if count < 0: 
            print(f"duplicated url: {url}  , downloaded about {abs(count)}\n")
                    
    logging.info(f"Number of duplicate downloads: {duplicates}")
    
    return url_counts