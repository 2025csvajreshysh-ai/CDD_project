from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    user_id: Optional[int] = None
    restaurant_id: Optional[int] = None
    conversation_history: Optional[List[Dict[str, str]]] = None

    @field_validator("message")
    @classmethod
    def message_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value

class ChatItemAction(BaseModel):
    food_id: int
    name: str
    price: float
    image_url: str
    restaurant_name: str
    is_veg: bool

class ChatResponse(BaseModel):
    reply: str
    suggestions: List[str] = []
    recommended_items: List[ChatItemAction] = []
    intent: Optional[str] = "general"
    llm_used: bool = False

class DemandPredictionItem(BaseModel):
    item_id: int
    item_name: str
    predicted_demand_next_day: int
    confidence_score: float
    recommended_prep_qty: int
    peak_hour: str

class RecommendationQuery(BaseModel):
    user_id: Optional[int] = None
    category_id: Optional[int] = None
    limit: int = 6
