from pydantic import BaseModel, Field, field_validator
from typing import Optional, Union, Literal
from datetime import datetime


# Question Type Models
# MongoDB Schema for incoming question data (not stored as-is, but parsed and stored in SQL)
class MCQQuestion(BaseModel):
    """Multiple Choice Question Schema"""
    type: Literal["mcq"] = Field(..., description="Question type")
    Q: str = Field(..., min_length=1, description="Question text")
    A: list[str] = Field(..., min_length=2, description="List of answer choices")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "mcq",
                "Q": "What is the capital of France?",
                "A": ["Paris", "London", "Berlin", "Madrid"]
            }
        }

# MongoDB Schema for True/False questions
class TFQuestion(BaseModel):
    """True/False Question Schema"""
    type: Literal["tf"] = Field(..., description="Question type")
    Q: str = Field(..., min_length=1, description="Question text")
    A: list[str] = Field(..., description="Answer choices (True/False)")
    
    @field_validator("A")
    @classmethod
    def validate_tf_answers(cls, v):
        """Ensure answers are exactly ['True', 'False']"""
        if len(v) != 2:
            raise ValueError("True/False questions must have exactly 2 answers")
        if set(v) != {"True", "False"}:
            raise ValueError("True/False questions must contain 'True' and 'False'")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "tf",
                "Q": "The earth is round",
                "A": ["True", "False"]
            }
        }

# MongoDB Schema for Open-ended questions
class OpenQuestion(BaseModel):
    """Open-ended Question Schema"""
    type: Literal["open"] = Field(..., description="Question type")
    Q: str = Field(..., min_length=1, description="Question text")
    A: list = Field(default_factory=list, description="Empty list for open-ended questions")
    
    @field_validator("A")
    @classmethod
    def validate_open_answers(cls, v):
        """Open-ended questions must have empty answers array"""
        if len(v) != 0:
            raise ValueError("Open-ended questions must have an empty answers list")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "open",
                "Q": "Explain your understanding of machine learning",
                "A": []
            }
        }


# Union type for all question types
QuestionData = Union[MCQQuestion, TFQuestion, OpenQuestion]


class QuestionListPayload(BaseModel):
    """Schema for incoming list of questions to parse (not stored)"""
    questions: list[QuestionData] = Field(..., min_length=1, description="List of questions to parse")
    metadata: Optional[dict] = Field(default=None, description="Optional metadata about the question set")
    
    class Config:
        json_schema_extra = {
            "example": {
                "questions": [
                    {
                        "type": "mcq",
                        "Q": "What is 2+2?",
                        "A": ["3", "4", "5", "6"]
                    },
                    {
                        "type": "tf",
                        "Q": "The earth is round",
                        "A": ["True", "False"]
                    },
                    {
                        "type": "open",
                        "Q": "Explain artificial intelligence",
                        "A": []
                    }
                ],
                "metadata": {"subject": "Science", "difficulty": "medium"}
            }
        }


class ParsedQuestion(BaseModel):
    """Response schema for parsed questions"""
    question_index: int = Field(..., description="Index of the question in the list")
    type: str
    Q: str
    A: list
    
    class Config:
        json_schema_extra = {
            "example": {
                "question_index": 0,
                "type": "mcq",
                "Q": "What is 2+2?",
                "A": ["3", "4", "5", "6"]
            }
        }


class StoredQuestionsResponse(BaseModel):
    """Response for stored questions"""
    id: str = Field(..., description="Document ID")
    questions: list[ParsedQuestion]
    metadata: Optional[dict]
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "questions": [
                    {"question_index": 0, "type": "mcq", "Q": "What is 2+2?", "A": ["3", "4", "5", "6"]},
                    {"question_index": 1, "type": "tf", "Q": "The earth is round", "A": ["True", "False"]}
                ],
                "metadata": {"subject": "Science"},
                "created_at": "2024-03-26T10:30:00"
            }
        }


class UserAnswer(BaseModel):
    """Schema for user response to a question"""
    question_index: int = Field(..., description="Index of the question being answered")
    question_type: Literal["mcq", "tf", "open"] = Field(..., description="Type of the question")
    user_answer: str = Field(..., description="User's answer/response")


class QuestionAnswerPayload(BaseModel):
    """Schema for storing user answers to questions"""
    session_id: str = Field(..., description="Session or user identifier")
    answers: list[UserAnswer] = Field(..., min_length=1, description="List of user answers")
    metadata: Optional[dict] = Field(default=None, description="Optional metadata")


class StoredAnswerResponse(BaseModel):
    """Response for stored answers"""
    id: str = Field(..., description="Document/Record ID")
    session_id: str
    answers: list[UserAnswer]
    metadata: Optional[dict]
    created_at: datetime
