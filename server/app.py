# ================================================================
# FILE: server/app.py
# PURPOSE: Entry point for OpenEnv multi-mode deployment
# Required by OpenEnv validation!
# ================================================================


from app.main import app
import uvicorn

def main():
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=7860,
        workers=1
    )

if __name__ == "__main__":
    main()

__all__ = ["app", "main"]