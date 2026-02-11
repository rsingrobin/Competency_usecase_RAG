from sqlalchemy import text
from app.db import SessionLocal
import re

def can_start_competency(employee_id, competency_id):
    session = SessionLocal()

    prereq = session.execute(text("""
        SELECT pre_requisite_id
        FROM competency_catalog
        WHERE competency_id=:cid
    """), {"cid": competency_id}).fetchone()

    # No prerequisite
    if not prereq:
        session.close()
        return True

    prereq_id = prereq._mapping["pre_requisite_id"]

    if not prereq_id:
        session.close()
        return True

    status = session.execute(text("""
        SELECT status
        FROM employee_competency
        WHERE employee_id=:eid
        AND competency_id=:pid
    """), {
        "eid": employee_id,
        "pid": prereq_id
    }).fetchone()

    session.close()

    if not status:
        return False

    return status._mapping["status"] == "COMPLETED"

def get_next_competency(employee_id):
    session = SessionLocal()

    rows = session.execute(text("""
        SELECT c.competency_id,
               c.competency_name,
               c.pre_requisite_id
        FROM competency_catalog c
        WHERE c.competency_id NOT IN (
            SELECT competency_id
            FROM employee_competency
            WHERE employee_id=:eid
            AND status='COMPLETED'
        )
    """), {"eid": employee_id}).fetchall()

    for r in rows:
        m = r._mapping
        prereq = m["pre_requisite_id"]

        if prereq is None:
            session.close()
            return m

        status = session.execute(text("""
            SELECT status
            FROM employee_competency
            WHERE employee_id=:eid
            AND competency_id=:pid
        """), {
            "eid": employee_id,
            "pid": prereq
        }).fetchone()

        if status and status._mapping["status"] == "COMPLETED":
            session.close()
            return m

    session.close()
    return None

from sqlalchemy import text
from app.db import SessionLocal


def get_competency_path(name):
    session = SessionLocal()

    rows = session.execute(text("""
        SELECT competency_id,
               competency_name,
               proficiency_level_name,
               pre_requisite_id
        FROM competency_catalog
        WHERE competency_name ILIKE :name
        ORDER BY  CAST(
                regexp_replace(
                    proficiency_level_name,
                    '[^0-9]',
                    '',
                    'g'
                ) AS INT
            )

    """), {"name": f"%{name}%"}).fetchall()

    session.close()

    return [dict(r._mapping) for r in rows]

from sqlalchemy import text
from app.db import SessionLocal


def get_competency_path_from_question(question: str):
    session = SessionLocal()

    # Find competency referenced in question
    comp = session.execute(text("""
        SELECT DISTINCT competency_name
        FROM competency_catalog
        WHERE :q ILIKE '%' || competency_name || '%'
        LIMIT 1
    """), {"q": question}).fetchone()

    if not comp:
        session.close()
        return []

    comp_name = comp._mapping["competency_name"]

    # Fetch all levels of that competency
    rows = session.execute(text("""
        SELECT competency_id,
               competency_name,
               proficiency_level_name
        FROM competency_catalog
        WHERE competency_name = :name
        ORDER BY
            CAST(
                regexp_replace(
                    proficiency_level_name,
                    '[^0-9]',
                    '',
                    'g'
                ) AS INT
            )
    """), {"name": comp_name}).fetchall()

    session.close()

    return [dict(r._mapping) for r in rows]


def get_sequence_until_level(question: str):
    session = SessionLocal()

    try:
        # Extract requested level (E1 etc.)
        match = re.search(r'E\d+', question, re.IGNORECASE)
        target_level = match.group(0).upper() if match else None

        # Find competency mentioned
        comp = session.execute(text("""
            SELECT competency_name
            FROM competency_catalog
            WHERE :q ILIKE '%' || competency_name || '%'
            LIMIT 1
        """), {"q": question}).fetchone()

        if not comp:
            return None

        comp_name = comp._mapping["competency_name"]

        # Fetch all levels
        rows = session.execute(text("""
            SELECT proficiency_level_name
            FROM competency_catalog
            WHERE competency_name = :name
        """), {"name": comp_name}).fetchall()

        # Deduplicate + sort numerically
        levels = sorted(
            {r._mapping["proficiency_level_name"] for r in rows},
            key=lambda x: int(re.sub(r"\D", "", x or "0") or 0)
        )

        if not target_level or target_level not in levels:
            return comp_name, levels

        idx = levels.index(target_level)

        return comp_name, levels[:idx + 1]

    finally:
        session.close()
