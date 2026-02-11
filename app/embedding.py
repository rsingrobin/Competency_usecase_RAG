import requests
import os
from dotenv import load_dotenv
from pgvector.sqlalchemy import Vector

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL")

def get_embedding(text: str) ->str:
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={
            "model": "nomic-embed-text",
            "prompt": text
        }
    )
    response.raise_for_status()

    embedding = response.json()["embedding"]
    return "[" + ",".join(map(str, embedding)) + "]"