"""Run `python -m a3_activity` to preview the existing UI on FastAPI."""
import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run("a3_activity.demo:app", host="127.0.0.1", port=int(os.environ.get("PORT", "3000")), workers=1)
