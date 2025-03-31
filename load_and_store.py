import time
import random
import logging
from datetime import datetime, timedelta
import instaloader
from new_read_data import get_column_data

# Configure logging for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Custom RateController to log wait times and potentially add extra backoff strategies.
class MyRateController(instaloader.RateController):
    def sleep(self, secs: float):
        # Log the sleep time for diagnostics.
        logging.info("Sleeping for {:.2f} seconds due to rate limiting...".format(secs))
        time.sleep(secs)

def batch_post_downloads():

    loader = instaloader.Instaloader(
        save_metadata=False,
        sanitize_paths=True,
        fatal_status_codes=[302, 400, 401],
        rate_controller=lambda ctx: MyRateController(ctx)
    )
    
    # Get post URLs from the provided Excel files.
    file_paths = [
        './ConversationStreamDistribution/ConversationStreamDistribution_3d42a086-f00d-490c-86c6-39c6b783c1b0_2.xlsx',
        './ConversationStreamDistribution/ConversationStreamDistribution_ac4cea66-b9fb-4b10-8023-d032dc646d1f_1.xlsx'
    ]
    post_urls = get_column_data(file_paths)
    
    post_num = 0
    total_posts = len(post_urls)
    logging.info("Starting download of {} posts.".format(total_posts))
    
    for post_url in post_urls:
        try:
            # Extract post shortcode from URL
            post_id = post_url.split("/")[-2]
            post = instaloader.Post.from_shortcode(loader.context, post_id)
            
            # Download the post using a target directory that includes the post number.
            target_folder = "./DownloadedPosts/Post_{}".format(post_num)
            loader.download_post(post, target=target_folder)
            post_num += 1
            
            #small random delay between downloads to mimic natural behavior.
            delay = random.uniform(2, 5)  
            logging.info("Downloaded post {}. Waiting {:.2f} seconds before next request.".format(post_num, delay))
            time.sleep(delay)
        

       
        
        except Exception as e:
            #log type of exception
            logging.error("Exception type: {}".format(type(e).__name__))
            # Log any other exceptions and optionally mark the post for later retry.
            logging.error("Failed to download post at URL {}: {}".format(post_url, e))
            
            with open("failed_urls.txt", "a") as file:
                file.write(post_url + "\n")
            
            continue

if __name__ == "__main__":
    batch_post_downloads()
