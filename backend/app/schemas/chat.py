from pydantic import BaseModel, Field
from typing import  Optional

class MessageCreate(BaseModel):
    '''
    Schema for creating a new chat message
    Used to validate the request body
    '''
    
    content : str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The content of the message by student"
        )
    
    session_id : str = Field(
        ...,
        description="The ID of the chat session this message belongs to"
    )
    
class MessageResponse(BaseModel):
    '''
    Schema for the response of a chat message in API responses
    '''
    
    message_id : str 
    role: str
    content : str
    created_at : str
    
    