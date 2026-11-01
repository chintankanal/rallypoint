import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8000"))

class Handler(SimpleHTTPRequestHandler):
    pass

server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
print(f"Serving US travelogue on port {PORT}", flush=True)
server.serve_forever()
