"""Local standard-library web server for the Datacom Kudos demonstration."""
import http.cookies
import json
import logging
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from store import Store, Problem

ROOT = Path(__file__).resolve().parent
DB_PATH = os.environ.get('KUDOS_DB', str(ROOT / 'kudos.db'))
store = Store(DB_PATH)
logging.basicConfig(level=logging.INFO)


class Handler(BaseHTTPRequestHandler):
    def json_reply(self, status, value, cookie=None):
        blob = json.dumps(value).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(blob)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie is not None:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(blob)

    def cookie_token(self):
        cookie = http.cookies.SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            return cookie['session'].value if 'session' in cookie else None
        except http.cookies.CookieError:
            return None

    def user(self):
        user = store.current_user(self.cookie_token())
        if not user:
            raise Problem(401, 'Please log in')
        return user

    def admin(self):
        user = self.user()
        if user['role'] != 'admin':
            raise Problem(403, 'Administrator access required')
        return user

    def body(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length < 1 or length > 8192:
            raise Problem(400, 'Invalid request size')
        try:
            data = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            raise Problem(400, 'Invalid JSON')
        if not isinstance(data, dict):
            raise Problem(400, 'Expected a JSON object')
        return data

    def check_origin(self):
        origin = self.headers.get('Origin')
        if origin:
            host = self.headers.get('Host', '')
            if origin not in (f'http://{host}', f'https://{host}'):
                raise Problem(403, 'Unexpected request origin')

    def route(self, method):
        parsed = urlsplit(self.path)
        path = parsed.path
        if method == 'GET' and path in ('/', '/index.html', '/app.js', '/styles.css'):
            name = 'index.html' if path == '/' else path.lstrip('/')
            file = ROOT / 'static' / name
            kind = {'index.html':'text/html; charset=utf-8',
                    'app.js':'text/javascript; charset=utf-8',
                    'styles.css':'text/css; charset=utf-8'}[name]
            data = file.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)
            return
        if method != 'GET':
            self.check_origin()
        if method == 'POST' and path == '/api/login':
            body = self.body()
            token, user = store.authenticate(body.get('email'), body.get('password'))
            self.json_reply(200, {'user': user}, f'session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=28800')
        elif method == 'POST' and path == '/api/logout':
            self.user()
            store.logout(self.cookie_token())
            self.json_reply(200, {'ok': True}, 'session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')
        elif method == 'GET' and path == '/api/me':
            self.json_reply(200, {'user': self.user()})
        elif method == 'GET' and path == '/api/users':
            self.json_reply(200, {'users': store.colleagues(self.user()['id'])})
        elif method == 'GET' and path == '/api/kudos':
            self.user()
            try:
                page = int(parse_qs(parsed.query).get('page', ['1'])[0])
            except ValueError:
                raise Problem(400, 'Invalid page number')
            self.json_reply(200, {'kudos': store.feed(page)})
        elif method == 'POST' and path == '/api/kudos':
            user = self.user()
            body = self.body()
            kudos_id = store.create_kudos(user['id'], body.get('recipient_id'), body.get('message'))
            self.json_reply(201, {'id': kudos_id})
        elif method == 'GET' and path == '/api/admin/kudos':
            self.admin()
            self.json_reply(200, {'kudos': store.feed(1, admin=True)})
        elif path.startswith('/api/admin/kudos/') and method in ('PATCH', 'DELETE'):
            admin = self.admin()
            try:
                kudos_id = int(path.rsplit('/',1)[1])
                if kudos_id < 1:
                    raise ValueError()
            except ValueError:
                raise Problem(400, 'Invalid kudos ID')
            if method == 'DELETE':
                store.delete(kudos_id)
            else:
                body = self.body()
                store.moderate(admin['id'], kudos_id, body.get('is_visible'), body.get('reason', ''))
            self.json_reply(200, {'ok': True})
        else:
            raise Problem(404, 'Not found')

    def handle_request(self, method):
        try:
            self.route(method)
        except Problem as error:
            self.json_reply(error.code, {'error': error.message})
        except (ValueError, TypeError):
            self.json_reply(400, {'error': 'Invalid request'})
        except Exception:
            logging.exception('Unexpected request failure')
            self.json_reply(500, {'error': 'Internal server error'})

    def do_GET(self): self.handle_request('GET')
    def do_POST(self): self.handle_request('POST')
    def do_PATCH(self): self.handle_request('PATCH')
    def do_DELETE(self): self.handle_request('DELETE')


if __name__ == '__main__':
    print('Kudos portal: http://127.0.0.1:8000')
    ThreadingHTTPServer(('127.0.0.1',8000), Handler).serve_forever()
