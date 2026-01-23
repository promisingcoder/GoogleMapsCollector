"""
Start the FastAPI backend server
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "pb_decoder.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
