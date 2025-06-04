from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

import vllm.config
from database.database import engine, AsyncSessionLocal
from database.models import Base, User
from database.crud import create_user, authenticate_user
import vllm 
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):

    global llm
    global sampling_params

    llm = vllm.LLM(model="facebook/opt-125m")

    sampling_params = vllm.SamplingParams(
        temperature=0.7,
        top_p=0.95,
        max_tokens=100,     
    )

    # Create tables at startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # No teardown actions needed here

app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "FastAPI Login Server is running"}

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    message: str
    username: str

@app.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user with username and password
    """
    username = request.username.strip()
    password = request.password


    async with AsyncSessionLocal() as db:
    
        user = await authenticate_user(db, username, password)
        
        # Check if username exists
        if not user:
            raise HTTPException(
                status_code=401, 
                detail="Invalid username or password"
            )
        
        return LoginResponse(
            message="Login successful",
            username=username
        )

class MessageRequest(BaseModel):
    chatHistory: str
    message: str

class MessageResponse(BaseModel):
    message: str

@app.post("/message", response_model=MessageResponse)
async def login(request: MessageRequest):
    hist=request.chatHistory
    prompt=request.message
    
    final_prompt=f'You are V, a helpful AI assistant. Be friendly, accurate, and concise. Reference previous messages when relevant.\nChat history: {hist}\nCurrent message: {prompt}\nRespond naturally as V.'

    try:
        output = llm.generate(final_prompt, sampling_params)
        '''
        output
        [RequestOutput(request_id=0, prompt='the president of france is ?', prompt_token_ids=[2, 627, 394, 9, 6664, 2389, 16, 17487], 
        encoder_prompt=None, encoder_prompt_token_ids=None, prompt_logprobs=None, outputs=[CompletionOutput(index=0, 
        text='\nNo, the president of the united States isnt president of the united states.', 
        token_ids=[50118, 3084, 6, 5, 394, 9, 5, 10409, 532, 16, 3999, 394, 9, 5, 10409, 982, 4, 2], 
        cumulative_logprob=None, logprobs=None, finish_reason=stop, stop_reason=None)], finished=True, metrics=None, lora_request=None, 
        num_cached_tokens=0, multi_modal_placeholders={})]
        '''
        return MessageResponse(message=output[0].outputs[0].text)
    except Exception as e:
        print(e)
        raise HTTPException(
                status_code=500, 
                detail="Error in generating output"
            )
        

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)