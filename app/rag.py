from sqlalchemy import text
from pgvector.sqlalchemy import Vector
from app.db import SessionLocal
from app.embedding import get_embedding
import requests
import os
from app.embedding import get_embedding
from sqlalchemy import text
from app.db import SessionLocal
import ollama


OLLAMA_URL = os.getenv("OLLAMA_BASE_URL")

def retrieve_context(query: str, limit: int = 5):
    session = SessionLocal()
    query_embedding = get_embedding(query)

    results = session.execute(
        text("""
        SELECT competency_name,
               description,
               category,
               focus_area,
               proficiency_level_name
        FROM public.competency_catalog
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> :embedding
        LIMIT :limit
        """),
        {"embedding": query_embedding, "limit": limit}
    ).fetchall()

    session.close()
    return results

def generate_answer(query: str, context_rows):
    context_text = "\n\n".join([
        f"""
        Competency: {r.competency_name}
        Description: {r.description}
        Category: {r.category}
        Focus Area: {r.focus_area}
        Proficiency: {r.proficiency_level_name}
        """
        for r in context_rows
    ])

    prompt = f"""
    You are a competency assistant.
    Answer ONLY using the provided context.
    If information is not present, say:
    "I cannot find this information in the competency database."

Context:
{context_text}

Question:
{query}

Answer clearly and concisely using the context.
"""

    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False
        }
    )

    response.raise_for_status()
    return response.json()["response"]

def ask_question(question: str):
    session = SessionLocal()

    emb = get_embedding(question)

    rows = session.execute(text("""
        competency_id,
            competency_name,
            proficiency_level_name,
            focus_area,
            embedding <=> CAST(:emb AS vector) AS distance
        FROM competency_catalog
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:emb AS vector)
        LIMIT 5
    """), {"emb": emb}).fetchall()

    context = "\n".join([
        f"{r.competency_name}: {r.description}"
        for r in rows
    ])

    prompt = f"""
    You are a competency assistant.
    Answer ONLY using the provided context.
    If information is not present, say:
    "I cannot find this information in the competency database."

    Context:
    {context}

    Question:
    {question}
    """

    response = ollama.chat(
        model="llama3",
        messages=[{"role": "user", "content": prompt}]
    )

    session.close()

    return response["message"]["content"]