from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.api.v1.router import api_router as api_v1_router

app = FastAPI(
    title="Wajahni AI Backend",
    description="Production-ready RAG Engine for Academic Guidance",
    version="1.0.0"
)

# Configure CORS so your frontend UI can talk to the API seamlessly
origins = [
    "http://localhost:3000",    # Standard React / Next.js port
    "http://localhost:5173",    # Standard Vite port
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],       # Allows HTTP GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],       # Allows all custom headers (e.g., Auth tokens)
)

# Include the RAG routes under the /api prefix
app.include_router(api_router, prefix="/api")
app.include_router(api_v1_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"status": "online", "message": "Wajahni AI Nervous System is fully operational."}