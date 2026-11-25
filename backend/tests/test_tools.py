"""
Unit and Integration Tests for Function Calling Tools and Tool-Augmented Endpoint.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from app.services.tools import (
    calculate_study_score,
    generate_study_schedule,
    execute_registered_tool,
)


def test_calculate_study_score_success():
    """Verify calculate_study_score produces correct score calculations."""
    res = calculate_study_score(correct_answers=18, total_questions=20)
    assert res["percentage"] == 90.0
    assert res["letter_grade"] == "A"
    assert res["status"] == "Mastered"


def test_calculate_study_score_validation_errors():
    """Verify validation handling in calculate_study_score."""
    res_zero = calculate_study_score(correct_answers=5, total_questions=0)
    assert "error" in res_zero

    res_invalid = calculate_study_score(correct_answers=25, total_questions=20)
    assert "error" in res_invalid


def test_generate_study_schedule_success():
    """Verify generate_study_schedule builds study plan phases."""
    res = generate_study_schedule(subject="Organic Chemistry", days_until_exam=10, hours_per_day=2.0)
    assert res["subject"] == "Organic Chemistry"
    assert res["total_study_hours"] == 20.0
    assert "phase_1_core_review" in res["schedule_phases"]


def test_execute_registered_tool_dispatcher():
    """Verify tool execution dispatcher handles tool lookup."""
    res = execute_registered_tool(
        tool_name="calculate_study_score",
        arguments={"correct_answers": 15, "total_questions": 20},
    )
    assert res["percentage"] == 75.0

    res_unknown = execute_registered_tool("unknown_func", {})
    assert "error" in res_unknown


@pytest.mark.asyncio
@patch("app.api.chat.ai_service.chat", new_callable=AsyncMock)
async def test_tool_augmented_chat_endpoint_success(
    mock_ai_chat,
    client: AsyncClient,
    auth_headers: dict,
):
    """Verify POST /api/chat/sessions/{session_id}/tools endpoint flow."""
    # 1. Create a session
    sess_res = await client.post(
        "/api/chat/sessions",
        json={"title": "Tool Test Session"},
        headers=auth_headers,
    )
    assert sess_res.status_code == 201
    session_id = sess_res.json()["session_id"]

    # 2. Mock AI response containing executed tool calls
    mock_ai_chat.return_value = {
        "answer": "You scored 90% (Grade A). Excellent performance!",
        "tool_calls": [
            {
                "tool_name": "calculate_study_score",
                "arguments": {"correct_answers": 18, "total_questions": 20},
                "result": {
                    "correct_answers": 18,
                    "total_questions": 20,
                    "percentage": 90.0,
                    "letter_grade": "A",
                    "status": "Mastered",
                    "feedback": "Excellent mastery of the subject material!",
                },
            }
        ],
    }

    payload = {
        "prompt": "I got 18 out of 20 on my test. What is my score?"
    }

    # 3. Call endpoint
    response = await client.post(
        f"/api/chat/sessions/{session_id}/tools",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "90%" in data["answer"]
    assert len(data["tool_calls"]) == 1
    assert data["tool_calls"][0]["tool_name"] == "calculate_study_score"