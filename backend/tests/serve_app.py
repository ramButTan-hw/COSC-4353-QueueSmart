"""Start the actual app on an available loopback port for browser tests."""
import socket
import uvicorn

from app.main import app

listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(128)
print(f"http://127.0.0.1:{listener.getsockname()[1]}", flush=True)
server = uvicorn.Server(uvicorn.Config(app, log_level="error"))


@app.post("/__test/shutdown")
def shutdown():
    # Test-only runner: gracefully stop the real process, including Windows venv launchers.
    server.should_exit = True
    return {"stopping": True}


server.run(sockets=[listener])
