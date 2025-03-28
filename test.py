import instaloader 

# Create an instance of Instaloader
loader = instaloader.Instaloader()

#download post from url 
url = "https://www.instagram.com/p/DEQ4SyHxTbN/"

post = instaloader.Post.from_shortcode(loader.context, url.split("/")[-2])

post_num =0 

# Download the post
loader.download_post(post, target="Post-"+str(post_num))



