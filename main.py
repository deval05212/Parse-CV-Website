import argparse
import json
from email.parser import BytesParser
from email.policy import default as email_policy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from resume_parser_service import DependencyError, parse_resume_bytes


BASE_DIR = Path(__file__).resolve().parent
HOME_PAGE = BASE_DIR / "home.html"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5200


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
            filename, content_type, file_bytes = self._read_uploaded_pdf()
        except ValueError as exc:
            self._send_json(
                {"error": str(exc)},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if not filename:
            self._send_json(
                {"error": "Please choose a PDF file before parsing."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            result = parse_resume_bytes(
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
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

    def _read_uploaded_pdf(self) -> tuple[str, str, bytes]:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("Expected a multipart form upload.")

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length header.") from exc

        if content_length <= 0:
            raise ValueError("The uploaded request body was empty.")

        body = self.rfile.read(content_length)
        message = BytesParser(policy=email_policy).parsebytes(
            (
                f"Content-Type: {content_type}\r\n"
                "MIME-Version: 1.0\r\n"
                "\r\n"
            ).encode("utf-8")
            + body
        )

        if not message.is_multipart():
            raise ValueError("Invalid multipart form submission.")

        for part in message.iter_parts():
            if part.get_content_disposition() != "form-data":
                continue

            field_name = part.get_param("name", header="content-disposition")
            if field_name != "pdf":
                continue

            return (
                part.get_filename() or "",
                part.get_content_type() or "",
                part.get_payload(decode=True) or b"",
            )

        return ("", "", b"")

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
