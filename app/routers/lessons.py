from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth import get_current_user_uid
from app.services.lesson_service import (
    get_all_lessons,
    get_lesson_by_id,
    mark_lesson_complete,
    get_user_completed_lessons
)

router = APIRouter(prefix="/lessons", tags=["lessons"])

class LessonCompleteRequest(BaseModel):
    lesson_id: str
    quiz_answer: str

# Changed from @router.get("/") to @router.get("")
@router.get("")
async def list_lessons():
    """Public: list all lessons (no auth needed, but later might require subscription)."""
    lessons = get_all_lessons()
    return {"lessons": lessons}

@router.post("/complete")
async def complete_lesson(
    payload: LessonCompleteRequest,
    user_id: str = Depends(get_current_user_uid)
):
    """Mark lesson as complete if quiz answer is correct."""
    lesson = get_lesson_by_id(payload.lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    correct = lesson.get("quiz_correct_answer")
    is_correct = mark_lesson_complete(
        user_id=user_id,
        lesson_id=payload.lesson_id,
        user_answer=payload.quiz_answer,
        correct_answer=correct
    )
    if not is_correct:
        return {"status": "wrong_answer", "message": "Incorrect answer. Try again."}
    return {"status": "completed", "message": "Lesson completed!"}

@router.get("/progress")
async def user_progress(user_id: str = Depends(get_current_user_uid)):
    """Get list of completed lesson IDs for the authenticated user."""
    completed = get_user_completed_lessons(user_id)
    return {"user_id": user_id, "completed_lessons": completed}