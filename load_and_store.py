from read_data import get_column_data
import instaloader 

# Create an instance of Instaloader
loader = instaloader.Instaloader(save_metadata=False, sanitize_metadata=True, fatal_status_codes=[302, 400, 401, 429])

#download post from url 
url = "https://www.instagram.com/p/DEQ4SyHxTbN/"

post = instaloader.Post.from_shortcode(loader.context, url.split("/")[-2])

post_num =0 

# Download the post
loader.download_post(post, target="Post-"+str(post_num))


'''
file_paths = [
    './ConversationStreamDistribution/ConversationStreamDistribution_3d42a086-f00d-490c-86c6-39c6b783c1b0_2.xlsx',
    './ConversationStreamDistribution/ConversationStreamDistribution_ac4cea66-b9fb-4b10-8023-d032dc646d1f_1.xlsx'
]

print(len(get_column_data(file_paths)))

'''


