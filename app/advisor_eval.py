import re

def extract_competency_and_level(question: str):
    """
    Extract competency name and level from question.
    Example:
    'How to complete Azure (Level: E1)'
    """

    comp_match = re.search(r'complete\s+(.+?)\s*\(Level', question, re.I)
    level_match = re.search(r'Level:\s*(E\d+)', question, re.I)

    competency = comp_match.group(1) if comp_match else ""
    level = level_match.group(1) if level_match else ""

    return competency.strip(), level.strip()


def evaluate_answer(answer: str, competency: str, target_level: str):
    """
    Returns score between 0 and 1
    """

    answer = answer.lower()
    competency = competency.lower()
    target_level = target_level.lower()

    score = 0
    total_checks = 3

    # Check 1: competency name present
    if competency in answer:
        score += 1

    # Check 2: roadmap sequence present
    if any(lvl in answer for lvl in ["e0", "e1", "e2", "e3", "e4"]):
        score += 1

    # Check 3: target level mentioned
    if target_level in answer:
        score += 1

    return score / total_checks

def compute_answer_accuracy(question: str, answer: str):
    competency, level = extract_competency_and_level(question)

    if not competency or not level:
        return 0

    return evaluate_answer(answer, competency, level)