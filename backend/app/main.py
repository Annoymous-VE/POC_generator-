"""
FastAPI Application Entrypoint for POC Generator.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router

app = FastAPI(
    title="AI POC Generation Framework API",
    description="Backend API for adaptive POC document planning, generation, and rendering.",
    version="1.0.0",
)

# Configure CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "poc-generator-backend"}
