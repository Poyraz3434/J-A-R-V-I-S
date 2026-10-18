"""J.A.R.V.I.S. application entry point."""
import os
import sys

# Render'da çalışıyorsa → FastAPI
if os.getenv("RENDER") or os.getenv("API_MODE"):
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    
    app = FastAPI(title="JARVIS API", version="10.0")
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    def home():
        return {"status": "JARVIS v10 API Online", "version": "10.0"}
    
    @app.get("/health")
    def health():
        return {"alive": True}
    
    @app.post("/ask")
    def ask_jarvis(text: str):
        return {"answer": f"JARVIS: {text}"}
    
    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8000)

# Lokal: Desktop GUI
else:
    from jarvis_v10 import main
    main()