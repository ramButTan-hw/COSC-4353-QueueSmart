"""Start the FastAPI demo on an available loopback port for browser-adapter tests."""
import socket
import uvicorn
from a3_activity.demo import app


listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(128)
print(f"http://127.0.0.1:{listener.getsockname()[1]}", flush=True)
uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", log_level="error")).run(sockets=[listener])
