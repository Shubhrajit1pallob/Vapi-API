from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from datetime import datetime
from backend.app.core.database import get_database
from backend.app.core.security import verify_api_key
from backend.app.models.mongoDB_schemas import (
    QuestionListPayload,
    ParsedQuestion,
    QuestionAnswerPayload,
)

router = APIRouter(prefix="/api", tags=["questions"])


@router.post("/questions", response_model=dict, dependencies=[Depends(verify_api_key)])
async def create_questions(payload: QuestionListPayload, db=Depends(get_database)):
    """
    Receive, parse, validate, and STORE questions in the database.
    Requires X-API-Key header authentication.
    """
    try:
        parsed_questions = []
        
        for index, question in enumerate(payload.questions):
            parsed_q = ParsedQuestion(
                question_index=index,
                type=question.type,
                Q=question.Q,
                A=question.A
            )
            parsed_questions.append(parsed_q)
        
        # Store questions in MongoDB
        document = {
            "questions": [q.model_dump() for q in parsed_questions],
            "metadata": payload.metadata,
            "created_at": datetime.now()
        }
        
        result = db.questions_collection.insert_one(document)
        
        return {
            "success": True,
            "message": "Questions stored successfully",
            "id": str(result.inserted_id),
            "total_questions": len(parsed_questions)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error storing questions: {str(e)}"
        )


@router.get("/questions", dependencies=[Depends(verify_api_key)])
async def get_all_questions(
    limit: int = 10, 
    skip: int = 0,
    db=Depends(get_database)
):
    """
    Retrieve all stored question sets with pagination.
    Requires X-API-Key header authentication.
    """
    try:
        cursor = db.questions_collection.find().skip(skip).limit(limit)
        documents = []
        
        for doc in cursor:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            documents.append(doc)
        
        total = db.questions_collection.count_documents({})
        
        return {
            "success": True,
            "data": documents,
            "pagination": {
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving questions: {str(e)}"
        )


@router.get("/questions/{question_id}", dependencies=[Depends(verify_api_key)])
async def get_questions_by_id(question_id: str, db=Depends(get_database)):
    """
    Retrieve specific question set by ID.
    Requires X-API-Key header authentication.
    """
    try:
        # Validate ObjectId format
        obj_id = ObjectId(question_id)
        
        document = db.questions_collection.find_one({"_id": obj_id})
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questions not found"
            )
        
        document["id"] = str(document["_id"])
        del document["_id"]
        
        return {
            "success": True,
            "data": document
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid question ID: {str(e)}"
        )


@router.delete("/questions/{question_id}", dependencies=[Depends(verify_api_key)])
async def delete_questions(question_id: str, db=Depends(get_database)):
    """
    Delete question set by ID.
    Requires X-API-Key header authentication.
    """
    try:
        obj_id = ObjectId(question_id)
        
        result = db.questions_collection.delete_one({"_id": obj_id})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questions not found"
            )
        
        return {
            "success": True,
            "message": "Questions deleted successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting questions: {str(e)}"
        )


@router.post("/answers", response_model=dict, dependencies=[Depends(verify_api_key)])
async def store_answers(payload: QuestionAnswerPayload, db=Depends(get_database)):
    """
    Store user answers to questions.
    Requires X-API-Key header authentication.
    """
    try:
        # Insert user answers into MongoDB
        document = {
            "session_id": payload.session_id,
            "answers": [answer.model_dump() for answer in payload.answers],
            "metadata": payload.metadata,
            "created_at": datetime.now()
        }
        
        result = db.answers_collection.insert_one(document)
        
        return {
            "success": True,
            "message": "Answers stored successfully",
            "id": str(result.inserted_id)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error storing answers: {str(e)}"
        )


@router.get("/answers", dependencies=[Depends(verify_api_key)])
async def get_all_answers(
    limit: int = 10, 
    skip: int = 0,
    db=Depends(get_database)
):
    """
    Retrieve all stored user answers with pagination.
    Requires X-API-Key header authentication.
    """
    try:
        cursor = db.answers_collection.find().skip(skip).limit(limit)
        documents = []
        
        for doc in cursor:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            documents.append(doc)
        
        total = db.answers_collection.count_documents({})
        
        return {
            "success": True,
            "data": documents,
            "pagination": {
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving answers: {str(e)}"
        )


@router.get("/answers/{answer_id}", dependencies=[Depends(verify_api_key)])
async def get_answers_by_id(answer_id: str, db=Depends(get_database)):
    """
    Retrieve specific user answers by ID.
    Requires X-API-Key header authentication.
    """
    try:
        # Validate ObjectId format
        obj_id = ObjectId(answer_id)
        
        document = db.answers_collection.find_one({"_id": obj_id})
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Answers not found"
            )
        
        document["id"] = str(document["_id"])
        del document["_id"]
        
        return {
            "success": True,
            "data": document
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid answer ID: {str(e)}"
        )


@router.delete("/answers/{answer_id}", dependencies=[Depends(verify_api_key)])
async def delete_answers(answer_id: str, db=Depends(get_database)):
    """
    Delete user answers by ID.
    Requires X-API-Key header authentication.
    """
    try:
        obj_id = ObjectId(answer_id)
        
        result = db.answers_collection.delete_one({"_id": obj_id})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Answers not found"
            )
        
        return {
            "success": True,
            "message": "Answers deleted successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting answers: {str(e)}"
        )
