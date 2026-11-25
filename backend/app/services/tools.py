"""
Executable Tool Definitions and Tool Registry for Gemini Function Calling.
Contains deterministic functions for educational calculations and schedule generation.
"""
import logging
import math
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


def calculate_study_score(correct_answers: int, total_questions: int) -> Dict[str, Any]:
    """Calculates quiz percentage score, letter grade, and performance feedback.

    Args:
        correct_answers: Number of correct questions answered by student (ge 0).
        total_questions: Total number of questions in quiz (gt 0).

    Returns:
        Dict containing percentage, grade, status, and feedback.
    """
    if total_questions <= 0:
        return {"error": "total_questions must be greater than zero."}

    if correct_answers < 0 or correct_answers > total_questions:
        return {"error": "correct_answers must be between 0 and total_questions."}

    percentage = round((correct_answers / total_questions) * 100, 2)

    if percentage >= 90:
        grade = "A"
        status = "Mastered"
        feedback = "Excellent mastery of the subject material!"
    elif percentage >= 80:
        grade = "B"
        status = "Proficient"
        feedback = "Solid understanding. Review minor weak areas."
    elif percentage >= 70:
        grade = "C"
        status = "Developing"
        feedback = "Fair performance. Requires focused review before exam."
    elif percentage >= 60:
        grade = "D"
        status = "Needs Improvement"
        feedback = "Below target performance. Schedule dedicated study sessions."
    else:
        grade = "F"
        status = "At Risk"
        feedback = "Critical focus required. Re-read core concepts and seek tutoring."

    return {
        "correct_answers": correct_answers,
        "total_questions": total_questions,
        "percentage": percentage,
        "letter_grade": grade,
        "status": status,
        "feedback": feedback,
    }


def generate_study_schedule(
    subject: str, days_until_exam: int, hours_per_day: float = 2.0
) -> Dict[str, Any]:
    """Generates a structured daily study plan ahead of an upcoming exam.

    Args:
        subject: Name of the academic subject or topic.
        days_until_exam: Days remaining before the exam date (gt 0).
        hours_per_day: Daily study hours allocated (default 2.0).

    Returns:
        Dict containing total study hours, breakdown phase, and recommended focus areas.
    """
    if days_until_exam <= 0:
        return {"error": "days_until_exam must be greater than zero."}

    hours = max(0.5, min(12.0, float(hours_per_day)))
    total_study_hours = round(days_until_exam * hours, 1)

    review_days = math.ceil(days_until_exam * 0.6)
    practice_days = math.ceil(days_until_exam * 0.3)
    final_prep_days = max(1, days_until_exam - review_days - practice_days)

    return {
        "subject": subject,
        "days_until_exam": days_until_exam,
        "daily_hours": hours,
        "total_study_hours": total_study_hours,
        "schedule_phases": {
            "phase_1_core_review": f"Days 1-{review_days}: Intensive reading & note review ({round(review_days * hours, 1)} hrs)",
            "phase_2_practice_testing": f"Days {review_days + 1}-{review_days + practice_days}: Practice exams & flashcards ({round(practice_days * hours, 1)} hrs)",
            "phase_3_final_polish": f"Final {final_prep_days} Day(s): Light review & rest before exam ({round(final_prep_days * hours, 1)} hrs)",
        },
    }


# Central registry mapping tool function names to Python callables
STUDY_TOOLS_MAP: Dict[str, Callable[..., Dict[str, Any]]] = {
    "calculate_study_score": calculate_study_score,
    "generate_study_schedule": generate_study_schedule,
}

# List of tool functions passed into Gemini GenerateContentConfig
REGISTERED_GEMINI_TOOLS: List[Callable] = [
    calculate_study_score,
    generate_study_schedule,
]


def execute_registered_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Look up and execute a registered tool by function name."""
    tool_func = STUDY_TOOLS_MAP.get(tool_name)
    if not tool_func:
        logger.error(f"Attempted execution of unregistered tool: {tool_name}")
        return {"error": f"Unknown tool name: {tool_name}"}

    try:
        logger.info(f"Executing tool '{tool_name}' with arguments: {arguments}")
        result = tool_func(**arguments)
        return result
    except Exception as exc:
        logger.error(f"Error executing tool '{tool_name}': {exc}", exc_info=True)
        return {"error": f"Tool execution failed: {str(exc)}"}