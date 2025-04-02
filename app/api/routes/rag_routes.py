from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.rag_service import get_rag_answer

router = APIRouter()

class QuestionRequest(BaseModel):
    question: str

class AnswerResponse(BaseModel):
    answer: str

@router.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    try:
        answer = await get_rag_answer(request.question)
        return AnswerResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
