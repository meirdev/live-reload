import argparse
import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect
from watchfiles import awatch


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    dir: Path = Path.cwd()

    def url(self, protocol: str = "http") -> str:
        return f"{protocol}://{self.host}:{self.port}"


settings = Settings()


app = FastAPI()

connections: set[WebSocket] = set()


async def notify_connections(dir: Path):
    async for _ in awatch(dir):
        for connection in connections:
            await connection.send_text("reload")


def inject_script(file_path: Path) -> str:
    script_js = """<script type="text/javascript" src="{url}/___inject_script.js"></script>""".format(
        url=settings.url()
    )

    with file_path.open() as fp:
        html = fp.read()

        for tag in ["head", "body", "html", "!DOCTYPE"]:
            if match := re.search(f"<{tag}[^>]*>", html, flags=re.IGNORECASE):
                html = html[: match.end()] + script_js + html[match.end() :]
                break
        else:
            html = script_js + html

        return html


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(notify_connections(settings.dir))


@app.websocket("/___ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.add(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connections.remove(websocket)


@app.get("/___inject_script.js")
async def inject_script_js():
    script = """
    (function () {
        var ws = new WebSocket(`$url/___ws`);
        ws.onmessage = function (event) {
            if (event.data === "reload") {
                location.reload();
            }
        }
    })();
    """

    return Response(
        script.replace("$url", settings.url("ws")), media_type="text/javascript"
    )


@app.get("/{file:path}")
async def static_file(file: str):
    file_path = settings.dir / Path(file)

    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        file_path.resolve().relative_to(settings.dir)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if file_path.suffix in [".html", ".html"]:
        return HTMLResponse(inject_script(file_path))

    return FileResponse(file_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=settings.host, help="Host to listen on")
    parser.add_argument(
        "--port", default=settings.port, type=int, help="Port to listen on"
    )
    parser.add_argument(
        "dir", default=settings.dir, nargs="?", type=Path, help="Directory to serve"
    )

    args = parser.parse_args()

    settings.host = args.host
    settings.port = args.port
    settings.dir = args.dir.resolve()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
