import os
import time
import signal
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mimetypes
import magic
import tempfile
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

import vllm.config
from database.database import engine, AsyncSessionLocal
from database.models import Base, User
from database.crud import create_user, authenticate_user
import vllm 
import asyncio

import httpx
import subprocess

current_model = 'theqtcompany/codellama-7b-qml'
ollama_process = None

async def wait_for_ollama(max_retries=30, delay=1):
    """Wait for Ollama server to be ready"""
    for i in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    print("Ollama server is ready!")
                    return True
        except Exception as e:
            print(f"Waiting for Ollama server... ({i+1}/{max_retries})")
            await asyncio.sleep(delay)
    return False

async def pull_model(model_name: str) -> bool:
    """Pull a model using Ollama API"""
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout for model pulling
            response = await client.post(
                "http://localhost:11434/api/pull",
                json={"name": model_name},
                timeout=300.0
            )
            if response.status_code == 200:
                print(f"Model '{model_name}' pulled successfully via API.")
                return True
            else:
                print(f"Failed to pull model via API: {response.status_code}")
                return False
    except Exception as e:
        print(f"Error pulling model via API: {e}")
        # Fallback to CLI
        try:
            result = subprocess.run(["ollama", "pull", model_name], 
                                  check=True, capture_output=True, text=True, timeout=300)
            print(f"Model '{model_name}' pulled successfully via CLI.")
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"Failed to pull model via CLI: {e}")
            return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ollama_process, current_model

    try:
        print("Starting Ollama server...")
        # Start Ollama server in background
        ollama_process = subprocess.Popen(
            ["ollama", "serve"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid if os.name != 'nt' else None  # Create process group on Unix
        )
        
        # Wait for Ollama server to be ready
        if not await wait_for_ollama():
            raise RuntimeError("Ollama server failed to start within timeout period")
        
        # Pull the initial model
        if not await pull_model(current_model):
            print(f"Warning: Failed to pull initial model '{current_model}'. You may need to pull it manually.")
        
        print("Ollama server started successfully.")
        
    except Exception as e:
        print(f"Failed to start Ollama: {e}")
        if ollama_process:
            try:
                if os.name != 'nt':
                    os.killpg(os.getpgid(ollama_process.pid), signal.SIGTERM)
                else:
                    ollama_process.terminate()
            except:
                pass
        raise RuntimeError("Could not start Ollama server")

    # Create database tables at startup
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Database initialization error: {e}")
        
    yield
    
    # Cleanup
    if ollama_process and ollama_process.poll() is None:
        print("Shutting down Ollama server...")
        try:
            if os.name != 'nt':
                # Send SIGTERM to the process group
                os.killpg(os.getpgid(ollama_process.pid), signal.SIGTERM)
                ollama_process.wait(timeout=10)
            else:
                ollama_process.terminate()
                ollama_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print("Force killing Ollama server...")
            if os.name != 'nt':
                os.killpg(os.getpgid(ollama_process.pid), signal.SIGKILL)
            else:
                ollama_process.kill()
        except Exception as e:
            print(f"Error stopping Ollama: {e}")
        print("Ollama server stopped.")

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

class SwitchModelRequest(BaseModel):
    modelName: str

@app.post("/switch-model")
async def switch_model(request: SwitchModelRequest):
    global current_model

    model_id = request.modelName.strip()
    
    if not model_id:
        return JSONResponse({
            "status": "error",
            "message": "Model name cannot be empty"
        }, status_code=400)

    try:
        # Check if Ollama is running
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                await client.get("http://localhost:11434/api/tags")
            except Exception:
                return JSONResponse({
                    "status": "error",
                    "message": "Ollama server is not running"
                }, status_code=503)

        # Pull new model
        print(f"Pulling model: {model_id}")
        if not await pull_model(model_id):
            return JSONResponse({
                "status": "error",
                "message": f"Failed to pull model: {model_id}"
            }, status_code=500)

        # Update current model
        current_model = model_id

        return JSONResponse({
            "status": "success",
            "message": f"Successfully switched to model: {model_id}",
            "current_model": current_model
        })

    except Exception as e:
        print(f"Error switching model: {e}")
        return JSONResponse({
            "status": "error",
            "message": f"Failed to switch model: {str(e)}"
        }, status_code=500)

class MessageRequest(BaseModel):
    chatHistory: str
    message: str

class MessageResponse(BaseModel):
    message: str

@app.post("/message", response_model=MessageResponse)
async def send_message(request: MessageRequest):
    """
    Send a message to the current Ollama model
    """
    history = request.chatHistory
    prompt = request.message
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    final_prompt=prompt

    print(current_model)

    if current_model=='theqtcompany/codellama-7b-qml':
        final_prompt=f'<PRE>{prompt}<MID>'
    elif current_model=='llama3.1:8b':
        final_prompt= f"""You are a helpful AI assistant. Provide accurate, concise, and engaging responses.
GUIDELINES:

Be conversational and friendly while staying professional
Give direct answers with relevant context
Acknowledge uncertainty rather than guessing
Use chat history to maintain context and avoid repetition
Ask clarifying questions when needed

CHAT HISTORY:
{history if history else "No previous conversation"}
CURRENT USER MESSAGE:
{prompt}
Respond helpfully to the user's message, referencing previous conversation when relevant."""

    print(final_prompt)
    try:
        # Check if Ollama is running
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Test connection first
            try:
                await client.get("http://localhost:11434/api/tags", timeout=5.0)
            except Exception:
                raise HTTPException(status_code=503, detail="Ollama server is not responding")
            
            # Send the generation request
            print(f"Sending request to model: {current_model}")
            response = await client.post(
                url="http://localhost:11434/api/generate",
                json={
                    "model": current_model,
                    "prompt": final_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.95,
                        "max_tokens": 1000,
                        "stop": ["<SUF>", "<PRE>", "</PRE>", "</SUF>", "< EOT >", "\\end", "<MID>", "</MID>", "##"]
                    }
                },
                timeout=60.0
            )
            
            if response.status_code != 200:
                print(f"Ollama API error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Ollama API returned status {response.status_code}"
                )
            
            data = response.json()
            
            if "response" not in data:
                print(f"Unexpected response format: {data}")
                raise HTTPException(
                    status_code=500, 
                    detail="Invalid response format from Ollama"
                )
            
            ai_response = data["response"].strip()
            
            if not ai_response:
                ai_response = "I apologize, but I couldn't generate a response. Please try again."
            
            print(f"Generated response:\n {ai_response}")
            
            return MessageResponse(message=ai_response)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Ollama Error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating response: {str(e)}"
        )

@app.get("/models")
async def get_available_models():
    """
    Get list of available Ollama models
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [model["name"] for model in data.get("models", [])]
                return JSONResponse({
                    "status": "success",
                    "models": models,
                    "current_model": current_model
                })
            else:
                return JSONResponse({
                    "status": "error",
                    "message": "Failed to fetch models"
                }, status_code=500)
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": f"Error fetching models: {str(e)}"
        }, status_code=500)

@app.get("/health")
async def health_check():
    """
    Check if Ollama server is running and current model is available
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check if Ollama is responding
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code != 200:
                return JSONResponse({
                    "status": "unhealthy",
                    "message": "Ollama server not responding"
                }, status_code=503)
            
            # Check if current model is available
            data = response.json()
            available_models = [model["name"] for model in data.get("models", [])]
            
            return JSONResponse({
                "status": "healthy",
                "ollama_running": True,
                "current_model": current_model,
                "model_available": current_model in available_models,
                "available_models": available_models
            })
            
    except Exception as e:
        return JSONResponse({
            "status": "unhealthy",
            "message": f"Health check failed: {str(e)}",
            "ollama_running": False
        }, status_code=503)

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