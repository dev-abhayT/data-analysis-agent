import uvicorn
from config.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("api:app", host="0.0.0.0", port=settings.port, reload=False)
