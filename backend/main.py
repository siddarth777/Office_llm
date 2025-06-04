from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from database.database import engine, AsyncSessionLocal
from database.models import Base, User
from database.crud import create_user, authenticate_user


class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    message: str
    username: str


@asynccontextmanager
async def lifespan(app: FastAPI):
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

@app.get("/")
async def root():
    return {"message": "FastAPI Login Server is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)