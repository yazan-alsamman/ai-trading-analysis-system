"""A stand-in for the LightOTP API (docs/otp.md), so capture_examples.py records the WhatsApp
code requests without a key, a credit or a real message. Start it, then start the backend with

    LIGHTOTP_TOKEN=fake LIGHTOTP_BASE_URL=http://localhost:8766

``POST /SendMessage`` keeps the code and answers ``{"id", "messageStatus": "Pending"}``;
``POST /CheckMessageStatus`` answers ``Delivered`` for a known id and 404 ``MessageNotFound``
otherwise. ``GET /__last?phone=+963...`` (this fake only) gives capture_examples.py the last
code and message id sent to a number. It never sees a real key.

    python docs/postman/tools/fake_lightotp.py [--port 8766]
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

SENT: dict[str, dict[str, str]] = {}  # message id -> message
LAST: dict[str, str] = {}  # phone -> last message id


class Handler(BaseHTTPRequestHandler):
    def _answer(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        if not self.headers.get("X-Api-Key"):
            self._answer(401, {"errorMessage": "ApiKeyNotFound"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/SendMessage":
            message_id = str(uuid.uuid4())
            SENT[message_id] = {
                "otpCode": str(body.get("otpCode", "")),
                "toPhoneE164": str(body.get("toPhoneE164", "")),
                "createdAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            }
            LAST[SENT[message_id]["toPhoneE164"]] = message_id
            self._answer(200, {"id": message_id, "messageStatus": "Pending"})
        elif self.path == "/CheckMessageStatus":
            message = SENT.get(str(body.get("id", "")))
            if message is None:
                self._answer(404, {"errorMessage": "MessageNotFound"})
                return
            self._answer(
                200,
                {
                    "id": body["id"],
                    "messageStatus": "Delivered",
                    "toPhoneE164": message["toPhoneE164"],
                    "createdAt": message["createdAt"],
                    "failureCode": None,
                    "failureTitle": None,
                    "failureReason": None,
                    "failedAt": None,
                },
            )
        else:
            self._answer(404, {"errorMessage": "NotFound"})

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        if url.path != "/__last":
            self._answer(404, {"errorMessage": "NotFound"})
            return
        phone = parse_qs(url.query).get("phone", [""])[0]
        message_id = LAST.get(phone)
        if message_id is None:
            self._answer(404, {"errorMessage": "MessageNotFound"})
            return
        self._answer(200, {"id": message_id, "otpCode": SENT[message_id]["otpCode"]})

    def log_message(self, *args) -> None:  # quiet
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    print(f"fake LightOTP on http://localhost:{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
