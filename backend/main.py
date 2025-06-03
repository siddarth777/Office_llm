from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# temp storage
USERS: Dict[str, str] = {
    "admin": "123",
    "siddarth":"123"
}

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
    
    # Check if username exists
    if username not in USERS:
        raise HTTPException(
            status_code=401, 
            detail="Invalid username or password"
        )
    
    # Check if password matches
    if USERS[username] != password:
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

@app.get("/users")
async def get_users():
    """
    Get list of available usernames (for testing purposes)
    """
    return {"users": list(USERS.keys())}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)