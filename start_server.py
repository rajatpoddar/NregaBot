import http.server
import socketserver
import threading
import time

PORT = 8099
class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'''<!DOCTYPE html>
<html>
<head>
    <title>Login</title>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <style>
        body { margin: 0; font-family: sans-serif; display: flex; height: 100vh; box-sizing: border-box; }
        .brand { background-color: #002D62; color: white; width: 50%; display: flex; align-items: center; justify-content: center; flex-direction: column; }
        .form-container { width: 50%; display: flex; align-items: center; justify-content: center; flex-direction: column; background: #f8f9fa; }
        @media(max-width: 768px) {
            body { flex-direction: column; }
            .brand { width: 100%; height: 200px; flex-shrink: 0; }
            .form-container { width: 100%; height: calc(100vh - 200px); }
        }
    </style>
</head>
<body>
    <div class='brand'>
        <h1>Welcome Back</h1>
    </div>
    <div class='form-container'>
        <h2>Sign In</h2>
        <form>
            <div style='margin-bottom: 10px;'><input type='email' placeholder='Email'></div>
            <div style='margin-bottom: 10px;'><input type='password' placeholder='Password'></div>
            <div><button type='submit'>Sign In</button></div>
        </form>
    </div>
</body>
</html>''')

socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('127.0.0.1', PORT), Handler)
t = threading.Thread(target=httpd.serve_forever, daemon=True)
t.start()
print("BACKGROUND SERVER RUNNING")
while True:
    time.sleep(1)
