import os

from fastapi import FastAPI, HTTPException,UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mimetypes
import magic
import tempfile
from typing import Dict,Optional

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

    #llm = vllm.LLM(model="facebook/opt-125m")

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
    
    final_prompt=f'You are V, a helpful AI assistant. Be friendly, accurate, and concise.\nmessage: {prompt}\n Respond naturally as V.'

    try:
        #output = llm.generate(final_prompt, sampling_params)
        '''
        output
        [RequestOutput(request_id=0, prompt='the president of france is ?', prompt_token_ids=[2, 627, 394, 9, 6664, 2389, 16, 17487], 
        encoder_prompt=None, encoder_prompt_token_ids=None, prompt_logprobs=None, outputs=[CompletionOutput(index=0, 
        text='\nNo, the president of the united States isnt president of the united states.', 
        token_ids=[50118, 3084, 6, 5, 394, 9, 5, 10409, 532, 16, 3999, 394, 9, 5, 10409, 982, 4, 2], 
        cumulative_logprob=None, logprobs=None, finish_reason=stop, stop_reason=None)], finished=True, metrics=None, lora_request=None, 
        num_cached_tokens=0, multi_modal_placeholders={})]
        '''
        #output[0].outputs[0].text
        return MessageResponse(message=final_prompt)
    except Exception as e:
        print(e)
        raise HTTPException(
                status_code=500, 
                detail="Error in generating output"
            )

class FileUploadResponse(BaseModel):
    response: str
    file_info: dict
    status: str

# File type detection function
def get_file_type_info(file_path: str, filename: str) -> dict:
    """
    Get comprehensive file type information
    """
    file_info = {}
    
    # Get file extension
    _, extension = os.path.splitext(filename)
    file_info['extension'] = extension.lower() if extension else 'No extension'
    
    # Get MIME type using mimetypes module
    mime_type, _ = mimetypes.guess_type(filename)
    file_info['mime_type'] = mime_type or 'Unknown'
    
    # Get file type using python-magic (more accurate)
    try:
        file_info['magic_type'] = magic.from_file(file_path)
        file_info['magic_mime'] = magic.from_file(file_path, mime=True)
    except Exception as e:
        file_info['magic_type'] = f'Error detecting: {str(e)}'
        file_info['magic_mime'] = 'Unknown'
    
    # Get file size
    file_info['size_bytes'] = os.path.getsize(file_path)
    file_info['size_mb'] = round(file_info['size_bytes'] / (1024 * 1024), 2)
    
    return file_info

@app.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload and analyze a file, then delete it
    """
    try:
        # Check if file is present
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Create temporary file path
        temp_dir = tempfile.gettempdir()
        # Use original filename but make it safe
        safe_filename = "".join(c for c in file.filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
        file_path = os.path.join(temp_dir, f"temp_{safe_filename}")
        
        try:
            # Save the file temporarily
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # Get file type information
            file_info = get_file_type_info(file_path, file.filename)
            
            # Create response message with file details
            response_message = f"""File Analysis Complete! 📁 File Details\\ Name: {file.filename}\\ Extension: {file_info['extension']}\\ Size:{file_info['size_mb']} MB ({file_info['size_bytes']:,} bytes)"""
            
            # Log file information (optional)
            print(f"File processed: {file.filename}")
            print(f"Extension: {file_info['extension']}")
            print(f"MIME Type: {file_info['mime_type']}")
            print(f"Magic Type: {file_info['magic_type']}")
            print(f"Size: {file_info['size_mb']} MB")
            
            return FileUploadResponse(
                response=response_message,
                file_info=file_info,
                status="success"
            )
            
        finally:
            # Always delete the file after processing
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"File deleted: {file_path}")
    
    except Exception as e:
        # Clean up file if it exists and there was an error
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        print(f"Error processing file: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"An error occurred while processing the file: {str(e)}"
        )
        

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)