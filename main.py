import argparse
import cgi
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from resume_parser_service import DependencyError, parse_resume_bytes


BASE_DIR = Path(__file__).resolve().parent
HOME_PAGE = BASE_DIR / "home.html"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class ResumeAPIHandler(BaseHTTPRequestHandler):
    server_version = "ResumeParserHTTP/1.0"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._set_default_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)

        if parsed_url.path in {"/", "/home.html"}:
            self._serve_home()
            return

        if parsed_url.path == "/health":
            self._send_json({"status": "ok"})
            return

        self._send_json(
            {"error": "Route not found."},
            status=HTTPStatus.NOT_FOUND,
        )

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)

        if parsed_url.path != "/api/parse-pdf":
            self._send_json(
                {"error": "Route not found."},
                status=HTTPStatus.NOT_FOUND,
            )
            return

        try:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                },
            )
        except ValueError:
            self._send_json(
                {"error": "Invalid multipart form submission."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        file_item = form["pdf"] if "pdf" in form else None
        if file_item is None or not getattr(file_item, "filename", ""):
            self._send_json(
                {"error": "Please choose a PDF file before parsing."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            result = parse_resume_bytes(
                file_bytes=file_item.file.read(),
                filename=file_item.filename,
                content_type=getattr(file_item, "type", "") or "",
            )
        except DependencyError as exc:
            self._send_json(
                {
                    "error": str(exc),
                    "hint": "Install the parser dependencies, then restart the backend.",
                },
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        except ValueError as exc:
            self._send_json(
                {"error": str(exc)},
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        except Exception as exc:
            self._send_json(
                {"error": f"Failed to parse the PDF: {exc}"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        self._send_json({"status": "success", **result})

    def log_message(self, format: str, *args) -> None:
        return

    def _serve_home(self) -> None:
        if not HOME_PAGE.exists():
            self._send_json(
                {"error": "home.html was not found."},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        content = HOME_PAGE.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._set_default_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._set_default_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _set_default_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    server = ThreadingHTTPServer((host, port), ResumeAPIHandler)
    print(f"Resume parser backend running at http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start the resume PDF upload backend and return parsed JSON."
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind the HTTP server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind the HTTP server")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
