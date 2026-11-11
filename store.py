"""SQLite persistence and business rules for the Datacom Kudos demonstration."""
import datetime as dt
import hashlib
import hmac
import secrets
import sqlite3

UTC = dt.timezone.utc


def now():
    return dt.datetime.now(UTC).isoformat()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 260000).hex()
    return f'{salt}${digest}'


def verify_password(password, hashed):
    try:
        salt, _ = hashed.split('$', 1)
        return hmac.compare_digest(password_hash(password, salt), hashed)
    except (ValueError, AttributeError):
        return False


class Problem(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Store:
    def __init__(self, path):
        self.path = str(path)
        self.initialize()

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def initialize(self):
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('employee','admin'))
                );
                CREATE TABLE IF NOT EXISTS kudos (
                    id INTEGER PRIMARY KEY,
                    sender_id INTEGER NOT NULL REFERENCES users(id),
                    recipient_id INTEGER NOT NULL REFERENCES users(id),
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_visible INTEGER NOT NULL DEFAULT 1 CHECK (is_visible IN (0,1)),
                    moderated_by INTEGER REFERENCES users(id),
                    moderated_at TEXT,
                    reason_for_moderation TEXT
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_kudos_time ON kudos(created_at DESC);
                CREATE INDEX IF NOT EXISTS ix_kudos_visible ON kudos(is_visible,created_at DESC);
                CREATE INDEX IF NOT EXISTS ix_kudos_sender ON kudos(sender_id,created_at DESC);
            ''')
            if not db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                for name, email, role in [
                    ('Alex Morgan','alex@example.test','employee'),
                    ('Jamie Lee','jamie@example.test','employee'),
                    ('Taylor Admin','admin@example.test','admin'),
                ]:
                    db.execute('INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)',
                               (name,email,password_hash('DemoPass123!'),role))

    def authenticate(self, email, password):
        with self.connect() as db:
            person = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            if not person or not verify_password(password, person['password_hash']):
                raise Problem(401, 'Invalid email or password')
            token = secrets.token_urlsafe(32)
            expiration = (dt.datetime.now(UTC)+dt.timedelta(hours=8)).isoformat()
            db.execute('INSERT INTO sessions VALUES (?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), person['id'], expiration))
            return token, self.public_user(person)

    @staticmethod
    def public_user(person):
        return {key: person[key] for key in ('id','name','email','role')}

    def current_user(self, token):
        if not token:
            return None
        with self.connect() as db:
            person = db.execute('''SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id
                                   WHERE token_hash=? AND expires_at>?''',
                                (hashlib.sha256(token.encode()).hexdigest(), now())).fetchone()
            return self.public_user(person) if person else None

    def logout(self, token):
        if token:
            with self.connect() as db:
                db.execute('DELETE FROM sessions WHERE token_hash=?',
                           (hashlib.sha256(token.encode()).hexdigest(),))

    def colleagues(self, user_id):
        with self.connect() as db:
            rows = db.execute('SELECT id,name FROM users WHERE id<>? ORDER BY name', (user_id,))
            return [dict(r) for r in rows]

    def create_kudos(self, sender_id, recipient_id, message):
        if not isinstance(recipient_id, int) or isinstance(recipient_id, bool):
            raise Problem(400, 'Select a colleague')
        if not isinstance(message, str) or not message.strip() or len(message.strip()) > 500:
            raise Problem(400, 'Message must contain 1 to 500 characters')
        msg = message.strip()
        if sender_id == recipient_id:
            raise Problem(400, 'You cannot send kudos to yourself')
        cutoff = (dt.datetime.now(UTC)-dt.timedelta(seconds=60)).isoformat()
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM users WHERE id=?', (recipient_id,)).fetchone():
                raise Problem(400, 'Selected colleague does not exist')
            duplicate = db.execute('''SELECT 1 FROM kudos WHERE sender_id=? AND recipient_id=?
                                      AND message=? AND created_at>=? LIMIT 1''',
                                   (sender_id,recipient_id,msg,cutoff)).fetchone()
            if duplicate:
                raise Problem(409, 'Duplicate kudos submitted too soon')
            count = db.execute('SELECT COUNT(*) FROM kudos WHERE sender_id=? AND created_at>=?',
                               (sender_id, cutoff)).fetchone()[0]
            if count >= 5:
                raise Problem(429, 'Too many kudos; please try again later')
            result = db.execute('''INSERT INTO kudos (sender_id,recipient_id,message,created_at)
                                   VALUES (?,?,?,?)''', (sender_id,recipient_id,msg,now()))
            return result.lastrowid

    def feed(self, page=1, admin=False):
        if not isinstance(page, int) or page < 1 or page > 100000:
            raise Problem(400, 'Invalid page number')
        where = '' if admin else 'WHERE k.is_visible=1'
        with self.connect() as db:
            rows = db.execute(f'''SELECT k.id,k.message,k.created_at,k.is_visible,k.moderated_at,
                                  k.reason_for_moderation,s.name AS sender,r.name AS recipient
                                  FROM kudos k JOIN users s ON s.id=k.sender_id
                                  JOIN users r ON r.id=k.recipient_id
                                  {where} ORDER BY k.created_at DESC,k.id DESC LIMIT 20 OFFSET ?''',
                              ((page-1)*20,))
            return [dict(row) for row in rows]

    def moderate(self, admin_id, kudos_id, visible, reason=''):
        if not isinstance(visible, bool):
            raise Problem(400, 'is_visible must be true or false')
        if not isinstance(reason, str) or len(reason) > 500:
            raise Problem(400, 'Reason must be 500 characters or less')
        with self.connect() as db:
            result = db.execute('''UPDATE kudos SET is_visible=?,moderated_by=?,moderated_at=?,
                                  reason_for_moderation=? WHERE id=?''',
                                (int(visible),admin_id,now(),reason.strip(),kudos_id))
            if result.rowcount == 0:
                raise Problem(404, 'Kudos not found')

    def delete(self, kudos_id):
        with self.connect() as db:
            result = db.execute('DELETE FROM kudos WHERE id=?', (kudos_id,))
            if result.rowcount == 0:
                raise Problem(404, 'Kudos not found')
