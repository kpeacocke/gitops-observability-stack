#!/usr/bin/env python3
"""Translate Alertmanager webhooks into Notifiarr Passthrough notifications."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


KEY_FILE = Path(os.environ.get("NOTIFIARR_KEY_FILE", "/run/secrets/notifiarr_passthrough_key"))
CHANNEL_ID = int(os.environ["NOTIFIARR_CHANNEL_ID"])
MAX_BODY = 1_048_576


def notifiarr_key() -> str:
    return KEY_FILE.read_text(encoding="utf-8").strip()


def alert_text(alert: dict) -> tuple[str, str]:
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    title = annotations.get("summary") or labels.get("alertname") or "Infrastructure alert"
    description = annotations.get("description") or annotations.get("message") or "No description supplied."
    details = []
    for key in ("severity", "instance", "job"):
        if labels.get(key):
            details.append(f"**{key.title()}:** {labels[key]}")
    if details:
        description = f"{description}\n\n" + " | ".join(details)
    return str(title)[:250], str(description)[:3500]


def notification(payload: dict) -> dict:
    status = payload.get("status", "firing")
    alerts = payload.get("alerts") or [{}]
    title, description = alert_text(alerts[0])
    extra = len(alerts) - 1
    if extra:
        description += f"\n\nPlus {extra} related alert(s) in this group."
    firing = status == "firing"
    return {
        "notification": {
            "update": True,
            "name": payload.get("groupKey") or title,
            "event": "Firing" if firing else "Resolved",
        },
        "discord": {
            "color": "dc3545" if firing else "28a745",
            "ping": {"pingUser": 0, "pingRole": 0},
            "images": {"thumbnail": "", "image": ""},
            "text": {
                "title": ("FIRING: " if firing else "RESOLVED: ") + title,
                "icon": "",
                "content": "",
                "description": description,
                "fields": [],
                "footer": "Prometheus Alertmanager",
            },
            "ids": {"channel": CHANNEL_ID},
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "alert-relay/1"

    def log_message(self, fmt: str, *args: object) -> None:
        # Never log request paths because the upstream API key is part of its URL.
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)

    def respond(self, code: int, message: str) -> None:
        body = (message + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self.respond(200 if self.path == "/health" else 404, "ok" if self.path == "/health" else "not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/alerts":
            self.respond(404, "not found")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_BODY:
                raise ValueError("invalid request size")
            incoming = json.loads(self.rfile.read(size))
            key = notifiarr_key()
            if not key:
                self.respond(503, "Notifiarr key is not provisioned")
                return
            data = json.dumps(notification(incoming)).encode()
            request = Request(
                f"https://notifiarr.com/api/v1/notification/passthrough/{key}",
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "ambitiouscake-alert-relay/1"},
                method="POST",
            )
            with urlopen(request, timeout=15) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"Notifiarr returned HTTP {response.status}")
            self.respond(202, "accepted")
        except (ValueError, json.JSONDecodeError) as error:
            self.respond(400, str(error))
        except (HTTPError, URLError, OSError, RuntimeError) as error:
            print(f"notification delivery failed: {type(error).__name__}", flush=True)
            self.respond(502, "notification delivery failed")


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
