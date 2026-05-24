import uvicorn

from .config_store import ConfigStore


if __name__ == "__main__":
    config = ConfigStore().get()
    server = config.get("server", {})
    uvicorn.run(
        "backend.app.main:app",
        host=server.get("host", "127.0.0.1"),
        port=int(server.get("port", 8787)),
        reload=False,
    )
