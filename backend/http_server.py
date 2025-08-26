# http_server.py
from http.server import HTTPServer, SimpleHTTPRequestHandler

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

httpd = HTTPServer(('0.0.0.0', 8000), CORSRequestHandler)
print("HTTP server started on http://localhost:8000")
httpd.serve_forever()