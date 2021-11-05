# Copyright 2021 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Fake (partial) Snap server to allow testing the HTTP-over-Unix-socket protocol."""

import http.server
import json
import os
import re
import socketserver
import tempfile
import threading
import urllib.parse


class Handler(http.server.BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        self.routes = [
            ("GET", re.compile(r"^/sections$"), self.get_sections),
        ]
        super().__init__(request, ("unix-socket", 80), server)

    def respond(self, resp, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp_json = json.dumps(resp, indent=4, sort_keys=True)
        self.wfile.write(resp_json.encode("utf-8"))

    def bad_request(self, message):
        d = {
            "result": {
                "message": message,
            },
            "status": "Bad Request",
            "status-code": 400,
            "type": "error",
        }
        self.respond(d, 400)

    def not_found(self):
        d = {
            "result": {"message": "invalid API endpoint requested"},
            "status": "Not Found",
            "status-code": 404,
            "type": "error",
        }
        self.respond(d, 404)

    def method_not_allowed(self):
        d = {
            "result": {"message": 'method "PUT" not allowed'},
            "status": "Method Not Allowed",
            "status-code": 405,
            "type": "error",
        }
        self.respond(d, 405)

    def internal_server_error(self, msg):
        d = {
            "result": {
                "message": f"internal server error: {msg}",
            },
            "status": "Internal Server Error",
            "status-code": 500,
            "type": "error",
        }
        self.respond(d, 500)

    def do_GET(self):  # noqa: N802
        self.do_request("GET")

    def do_POST(self):  # noqa: N802
        self.do_request("POST")

    def do_request(self, request_method):
        path, _, query = self.path.partition("?")
        path = urllib.parse.unquote(path)
        query = dict(urllib.parse.parse_qsl(query))

        if not path.startswith("/v1/"):
            self.not_found()
            return
        path = path[3:]

        allowed = []
        for method, regex, func in self.routes:
            match = regex.match(path)
            if match:
                if request_method == method:
                    data = self.read_body_json()
                    try:
                        func(match, query, data)
                    except Exception as e:
                        self.internal_server_error(e)
                        raise
                    return
                allowed.append(method)

        if allowed:
            self.method_not_allowed()
            return

        self.not_found()

    def read_body_json(self):
        try:
            content_len = int(self.headers.get("Content-Length", ""))
        except ValueError:
            content_len = 0
        if not content_len:
            return None
        body = self.rfile.read(content_len)
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        return json.loads(body)

    def get_sections(self, match, query, data):
        self.respond(
            {
                "type": "sync",
                "status-code": 200,
                "status": "OK",
                "result": {
                    [
                        "featured",
                        "database",
                        "ops",
                        "messaging",
                        "media",
                        "internet-of-things",
                    ]
                },
            }
        )


def start_server():
    socket_dir = tempfile.mkdtemp(prefix="test-ops.snap")
    socket_path = os.path.join(socket_dir, "test.socket")

    server = socketserver.UnixStreamServer(socket_path, Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()

    def shutdown():
        server.shutdown()
        server.server_close()
        thread.join()
        os.remove(socket_path)
        os.rmdir(socket_dir)

    return (shutdown, socket_path)


if __name__ == "__main__":
    import time

    shutdown, socket_path = start_server()
    print("Serving HTTP over socket", socket_path)

    # Wait forever (or till Ctrl-C pressed)
    try:
        while True:
            time.sleep(1)
    finally:
        shutdown()
