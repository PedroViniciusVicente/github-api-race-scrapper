import os
from dotenv import load_dotenv

def get_github_token():
    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    
    if not token:
        raise ValueError("Token do GitHub não encontrado. Verifique o arquivo .env.")
    return token
