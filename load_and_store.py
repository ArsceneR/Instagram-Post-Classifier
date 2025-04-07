import time
import random
import logging
import os
from datetime import datetime, timedelta
import instaloader
from new_read_data import get_column_data

# Configure logging for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Custom RateController to log wait times 
# maybe consider exponential/  add extra backoff strategies.
class MyRateController(instaloader.RateController):
    def sleep(self, secs: float):
        # Log the sleep time for diagnostics.
        logging.info("Sleeping for {:.2f} seconds due to rate limiting...".format(secs))
        time.sleep(secs)

def batch_post_downloads():

    loader = instaloader.Instaloader(
        sanitize_paths=True,
        fatal_status_codes=[302, 400],
        rate_controller=lambda ctx: MyRateController(ctx)
    )
    
    try: 
        loader.interactive_login("barbean_")
    except (instaloader.exceptions.BadCredentialsException, instaloader.exceptions.InvalidArgumentException) as e:
        logging.error("Login failed. Please check your username and password or ensure your account is not locked. Error: {}".format(e))
        return
    
    
    # Get post URLs from the provided Excel files.
    #do not change the ordder of the files. this will result in the index of the posts being off and halt the ability to map the posts correctly to a number. 
    file_paths = [
        './ConversationStreamDistribution/ConversationStreamDistribution_3d42a086-f00d-490c-86c6-39c6b783c1b0_2.xlsx',
        './ConversationStreamDistribution/ConversationStreamDistribution_ac4cea66-b9fb-4b10-8023-d032dc646d1f_1.xlsx'
    ]
    post_urls = get_column_data(file_paths)
    
    total_posts = len(post_urls)
    logging.info("Starting download of {} posts.".format(total_posts))
    
    start= 5574 #the post you want to start downloading from.
    
    # Iterate through each URL and download the corresponding post.
    for post_num in range(start,total_posts):
        post_url = post_urls[post_num].strip()  # Ensure no leading/trailing whitespace
        try:
            # Remove any trailing slash and extract shortcode
            clean_url = post_url.rstrip('/')
            parts = clean_url.split('/')
            if not post_url or len(parts) < 2:
                logging.error(f"Invalid URL format: {post_url}")
                with open("failed_urls.txt", "a", encoding="utf-8") as file:
                    file.write(post_url + "\n")
                continue

            post_shortcode = parts[-1] if parts[-1] else parts[-2]

            post = instaloader.Post.from_shortcode(loader.context, post_shortcode)
            
            #check if target directory exists 
            #instaloader already handles checking for exisiting posts and will skip downloading if it already exists. no need to double check here.
            post_dir = f"Post-{post_num}"
            
            loader.download_post(post, target=post_dir)
            
            delay = random.uniform(3, 6)
            logging.info(f"Downloaded post {post_num}/{total_posts}. Waiting {delay:.2f} seconds before next request.")
            time.sleep(delay)

            # Additional rate limiting every 1000 posts
            if post_num % 1000 == 0:
                long_delay = random.uniform(180, 300)
                logging.info(f"Reached {post_num} posts. Taking a longer break for {long_delay:.2f} seconds.")
                time.sleep(long_delay)
        except instaloader.exceptions.QueryReturnedNotFoundException as e:
            logging.error(f"Post not found for URL {post_url}: {e}")
            with open("failed_urls.txt", "a", encoding="utf-8") as file:
                file.write(post_url + "\n")
            continue
        except instaloader.exceptions.TooManyRequestsException as e:
            logging.error(f"Rate limit hit while processing URL {post_url}: {e}")
            time.sleep(random.uniform(300, 600))
            continue
        except Exception as e:
            logging.error(f"Exception type: {type(e).__name__} - Failed to download post at URL {post_url}: {e}")
            '''
        
                 if post_num == 1 and os.path.exists("failed_urls.txt"):
                # Clear the failed_urls.txt if it is the first post to avoid confusion
                os.remove("failed_urls.txt")
            '''
       
                
            with open("failed_urls.txt", "a", encoding="utf-8") as file:
                file.write(post_url + "\n")
                
            continue
    
    if post_num == 0:
        logging.warning("No posts were processed. Check the input URLs.")
        return
    failed_count = sum(1 for _ in open("failed_urls.txt", "r", encoding="utf-8"))
    logging.info(f"failed_count: {failed_count}")
    logging.info(f"Completed downloading {total_posts} posts with {failed_count} failures. Check 'failed_urls.txt' for details.")

if __name__ == "__main__":
    batch_post_downloads()