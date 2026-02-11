from fastapi import FastAPI, Form
from app.rag import retrieve_context, generate_answer, ask_question
from app.auth import login
from app.auth import get_employee , get_current_employee
from app.competency_service import can_start_competency
from app.competency_service import get_competency_path_from_question
from app.competency_service import get_competency_path
from app.competency_service import get_sequence_until_level
from app.db import SessionLocal
from sqlalchemy import text
import re
from app.competency_service import get_next_competency
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends


security = HTTPBearer()



app = FastAPI(title="Competency RAG API")

@app.get("/ask")
def ask(question: str):
    context = retrieve_context(question)
    answer = generate_answer(question, context)

    return {
        "question": question,
        "answer": answer,
        "sources": [
            {
                "competency_name": r.competency_name,
                "focus_area": r.focus_area,
                "proficiency": r.proficiency_level_name
            }
            for r in context
        ]
    }


@app.post("/login")
def login_api(
    email: str = Form(...),
    password: str = Form(...)
):
    token = login(email, password)

    if not token:
        return {"error": "Invalid credentials"}

    return {"token": token}


@app.post("/start")
def start_competency(token: str, competency_id: int):

    emp_id = get_employee(token)

    if not emp_id:
        return {"error": "Invalid session"}

    if not can_start_competency(emp_id, competency_id):
        return {"error": "Prerequisite not completed"}

    session = SessionLocal()

    session.execute(text("""
        INSERT INTO employee_competency(
            employee_id,
            competency_id,
            status,
            started_on
        )
        VALUES(:e,:c,'IN_PROGRESS',now())
        ON CONFLICT(employee_id, competency_id)
        DO UPDATE SET status='IN_PROGRESS'
    """), {"e": emp_id, "c": competency_id})

    session.commit()
    session.close()

    return {"message": "Competency started"}

@app.get("/roadmap")
def roadmap(token: str):
    emp_id = get_employee(token)

    if not emp_id:
        return {"error": "Invalid session"}

    next_comp = get_next_competency(emp_id)

    return {"next": next_comp}

@app.get("/my-competencies")
def my_competencies(employee_id: int = Depends(get_current_employee)):
    session = SessionLocal()

    try:
        rows = session.execute(text("""
            SELECT c.competency_id,
                   c.competency_name,
                   c.proficiency_level_name,
                   ec.status,
                   ec.progress
            FROM employee_competency ec
            JOIN competency_catalog c
              ON ec.competency_id = c.competency_id
            WHERE ec.employee_id = :eid
        GROUP BY
        c.competency_id,
        c.competency_name,
        c.proficiency_level_name,
        ec.status,
        ec.progress
        """), {"eid": employee_id}).fetchall()

        return [
            {
                "competency_id": r._mapping["competency_id"],
                "competency_name": r._mapping["competency_name"],
                "proficiency_level_name": r._mapping["proficiency_level_name"],
                "status": r._mapping["status"],
                "progress": r._mapping.get("progress", 0),
            }
            for r in rows
        ]

    finally:
        session.close()


@app.get("/learning-roadmap")
def learning_roadmap(employee_id: int = Depends(get_current_employee)):
    session = SessionLocal()

    try:
        rows = session.execute(text("""
            SELECT DISTINCT ON (c.competency_id)
                   c.competency_id,
                   c.competency_name,
                   c.proficiency_level_name
            FROM competency_catalog c
            LEFT JOIN employee_competency ec
              ON ec.competency_id = c.competency_id
              AND ec.employee_id = :eid
            WHERE (
                ec.status IS NULL
                OR LOWER(ec.status) != 'completed'
            )
            AND (
                c.pre_requisite_id IS NULL
                OR c.pre_requisite_id IN (
                    SELECT competency_id
                    FROM employee_competency
                    WHERE employee_id = :eid
                      AND LOWER(status) = 'completed'
                )
            )
            ORDER BY c.competency_id
            LIMIT 5
        """), {"eid": employee_id}).fetchall()

        return [
            {
                "competency_id": r._mapping["competency_id"],
                "competency_name": r._mapping["competency_name"],
                "proficiency_level_name": r._mapping["proficiency_level_name"],
            }
            for r in rows
        ]

    finally:
        session.close()


@app.get("/advisor")
def advisor(question: str, employee_id: int = Depends(get_current_employee)):
    roadmap_answer = build_learning_sequence(question)

    if roadmap_answer:
        return {"answer": roadmap_answer}
        # retrieve DB context
    context = retrieve_context(question)

    if not context:
        return {
            "answer": "No matching competency found in database."
        }

   # top matched competency
    comp = context[0]

    competency = comp.competency_name
    level = comp.proficiency_level_name

    # Step 2: build learning sequence
    roadmap_answer = build_learning_sequence_from_name(
        competency,
        level,
        employee_id,
    )

    if roadmap_answer:
        return {"answer": roadmap_answer}

    # fallback answer using DB context only
    answer = generate_answer(question, context)

    return {"answer": answer}


def build_learning_sequence(question: str):
    session = SessionLocal()

    try:
        # Extract competency name
        comp_match = re.search(r'complete\s+"?(.+?)"?\s*\(Level', question, re.I)
        level_match = re.search(r'Level:\s*(E\d+)', question, re.I)

        if not comp_match or not level_match:
            return None

        competency = comp_match.group(1).strip()
        target_level = level_match.group(1).upper()

        rows = session.execute(text("""
            SELECT DISTINCT
                competency_name,
                proficiency_level_name
            FROM competency_catalog
            WHERE competency_name = :name
        """), {"name": competency}).fetchall()

        if not rows:
            return None

        # Sort E0, E1, E2...
        levels = sorted(
            {r._mapping["proficiency_level_name"] for r in rows},
            key=lambda x: int(x[1:])
        )

        path = []
        for lvl in levels:
            path.append(
                f"{competency} (Level: {lvl})"
            )
            if lvl == target_level:
                break

        sequence = " → ".join(levels)

        answer = (
            f"Learning roadmap for {competency}:\n\n"
            f"{sequence}\n\n"
            f"To reach Level {target_level}, you must complete:\n"
            + "\n".join(path)
        )

        return answer

    finally:
        session.close()

def build_learning_sequence_from_name(
    competency,
    target_level,
    employee_id,
):
    session = SessionLocal()

    try:
        rows = session.execute(text("""
            SELECT DISTINCT proficiency_level_name
            FROM competency_catalog
            WHERE competency_name = :name
        """), {"name": competency}).fetchall()

        if not rows:
            return None

        levels = sorted(
            {r._mapping["proficiency_level_name"] for r in rows},
            key=lambda x: int(x[1:])
        )

        sequence = []
        for lvl in levels:
            sequence.append(lvl)
            if lvl == target_level:
                break

        roadmap_lines = [
            f"{competency} (Level: {lvl})"
            for lvl in sequence
        ]

        answer = (
            f"Learning roadmap for {competency}:\n\n"
            f"{' → '.join(sequence)}\n\n"
            f"To reach Level {target_level}, complete:\n"
            + "\n".join(roadmap_lines)
        )

        return answer

    finally:
        session.close()

