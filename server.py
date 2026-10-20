#!/usr/bin/env python3
"""Simple localhost server for the SIN -> LHR Flight Price Dashboard."""
import http.server
import socketserver
import webbrowser
import os

PORT = int(os.environ.get("PORT", 8080))

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}"
        print(f"Serving SIN -> LHR Flight Tracker Dashboard at {url}")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        httpd.serve_forever()
