from sqlalchemy import text
from db import SessionLocal
from embedding import get_embedding

def build_text(row):
    return f"""
    Competency Name: {row.competency_name}
    Description: {row.description}
    Category: {row.category}
    Focus Area: {row.focus_area}
    Sub Focus Area: {row.sub_focus_area}
    Microskills: {row.microskills}
    Proficiency Level: {row.proficiency_level_name}
    """

def ingest():
    session = SessionLocal()

    rows = session.execute(
        text("""
        SELECT competency_id,
               competency_name,
               description,
               category,
               focus_area,
               sub_focus_area,
               microskills,
               proficiency_level_name
        FROM public.competency_catalog
        WHERE embedding IS NULL
        """)
    ).fetchall()

    print(f"Found {len(rows)} rows to embed")

    for row in rows:
        combined_text = build_text(row)
        embedding = get_embedding(combined_text)
        print(f"Processing for {row}")
        session.execute(
            text("""
            UPDATE public.competency_catalog
            SET embedding = :embedding
            WHERE competency_id = :id
            """),
            {"embedding": embedding, "id": row.competency_id}
        )

    session.commit()
    session.close()

if __name__ == "__main__":
    ingest()