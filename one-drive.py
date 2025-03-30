from onedrivesdk import OneDriveClient, AuthProvider, HttpProvider, FileSystemTokenBackend

CLIENT_ID = 'your_client_id'
REDIRECT_URI = 'http://localhost:8080'

token_backend = FileSystemTokenBackend(token_path='token.json')
auth_provider = AuthProvider(token_backend=token_backend, client_id=CLIENT_ID, scopes=['wl.signin', 'wl.offline_access', 'onedrive.readwrite'])
http_provider = HttpProvider()
client = OneDriveClient('https://api.onedrive.com/v1.0/', auth_provider, http_provider)

auth_url = client.auth_provider.get_auth_url(REDIRECT_URI)
print(f"Go to the following URL to authenticate: {auth_url}")
code = input("Enter the authentication code here: ")
client.auth_provider.authenticate(code, REDIRECT_URI, CLIENT_ID)


file_path = '/path/to/your/file.txt'
file_name = 'file.txt'
with open(file_path, 'rb') as file:
    client.item(drive='me', path=file_name).upload(file)

print("File uploaded successfully!")