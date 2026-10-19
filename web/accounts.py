"""Persistent accounts, one-use invitations, revocable sessions and login limits."""
import hashlib
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from engine import connect_database

SESSION_SECONDS=12*3600


def digest(value):return hashlib.sha256(value.encode()).hexdigest()


def email_address(value):
    value=str(value or '').strip().lower()
    if len(value)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):
        raise ValueError('Informe um e-mail válido.')
    return value


def password_valid(value):
    if not isinstance(value,str) or not 12<=len(value)<=128:
        raise ValueError('Use uma senha com 12 a 128 caracteres.')
    return value


class Accounts:
    def __init__(self,root,max_users=50):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'accounts.sqlite';self.max_users=max_users
        self.dummy=generate_password_hash(secrets.token_urlsafe(32))
        with self.db() as db:db.executescript('''
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,password TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS invites(token TEXT PRIMARY KEY,email TEXT NOT NULL,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,csrf TEXT NOT NULL,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY,count INTEGER NOT NULL,expires REAL NOT NULL);
        ''')

    @contextmanager
    def db(self):
        db=connect_database(self.path)
        try:
            with db:yield db
        finally:db.close()

    def invite(self,email):
        email=email_address(email);token=secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('DELETE FROM invites WHERE email=? OR expires<?',(email,time.time()))
            db.execute('INSERT INTO invites VALUES(?,?,?)',(digest(token),email,time.time()+86400))
        return token

    def register(self,token,name,password):
        password_valid(password);name=str(name or '').strip()
        if not 2<=len(name)<=80:raise ValueError('Informe seu nome, com 2 a 80 caracteres.')
        hashed=generate_password_hash(password);uid=secrets.token_hex(16)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            invite=db.execute('SELECT * FROM invites WHERE token=? AND expires>?',(digest(str(token)),time.time())).fetchone()
            if not invite:raise ValueError('O convite expirou ou já foi usado. Solicite outro ao responsável pelo Radar.')
            if db.execute('SELECT COUNT(*) FROM users').fetchone()[0]>=self.max_users:
                raise ValueError('O limite de contas deste servidor foi atingido. Fale com o responsável pelo Radar.')
            try:db.execute('INSERT INTO users(id,email,name,password) VALUES(?,?,?,?)',(uid,invite['email'],name,hashed))
            except sqlite3.IntegrityError:raise ValueError('Não foi possível criar a conta. Fale com o responsável pelo Radar.') from None
            db.execute('DELETE FROM invites WHERE token=?',(digest(str(token)),))
        return uid

    def limited(self,key,maximum,seconds):
        key=digest(key);at=time.time()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM limits WHERE expires<?',(at,))
            row=db.execute('SELECT * FROM limits WHERE key=?',(key,)).fetchone()
            if row and row['count']>=maximum:return True
            db.execute('INSERT INTO limits VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1',(key,at+seconds))
        return False

    def login(self,email,password):
        email=str(email or '').strip().lower()
        with self.db() as db:user=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        if not isinstance(password,str) or len(password)>128:password='invalid'
        valid=check_password_hash(user['password'] if user else self.dummy,password)
        if not valid or not user or not user['enabled']:return None
        return self.new_session(user['id'])

    def new_session(self,uid):
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            # Bound simultaneous sessions; remove the oldest beyond the latest nine.
            db.execute('DELETE FROM sessions WHERE user_id=? AND token NOT IN (SELECT token FROM sessions WHERE user_id=? ORDER BY expires DESC LIMIT 9)',(uid,uid))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),uid,csrf,time.time()+SESSION_SECONDS))
        return token

    def session(self,token):
        if not token or len(token)>128:return None
        with self.db() as db:
            row=db.execute('SELECT users.id,users.email,users.name,sessions.csrf FROM sessions JOIN users ON users.id=sessions.user_id WHERE token=? AND expires>? AND enabled=1',(digest(token),time.time())).fetchone()
        return dict(row) if row else None

    def logout(self,token):
        with self.db() as db:db.execute('DELETE FROM sessions WHERE token=?',(digest(token or ''),))

    def change_password(self,uid,old,new):
        password_valid(new)
        with self.db() as db:
            row=db.execute('SELECT password FROM users WHERE id=?',(uid,)).fetchone()
        if not isinstance(old,str) or len(old)>128 or not row or not check_password_hash(row['password'],old):
            raise ValueError('A senha atual não confere.')
        self.reset_password(uid,new)

    def reset_password(self,uid,password):
        hashed=generate_password_hash(password_valid(password))
        with self.db() as db:
            if not db.execute('UPDATE users SET password=? WHERE id=?',(hashed,uid)).rowcount:raise ValueError('Conta não encontrada.')
            db.execute('DELETE FROM sessions WHERE user_id=?',(uid,))

    def set_enabled(self,uid,enabled):
        with self.db() as db:
            if not db.execute('UPDATE users SET enabled=? WHERE id=?',(int(enabled),uid)).rowcount:raise ValueError('Conta não encontrada.')
            db.execute('DELETE FROM sessions WHERE user_id=?',(uid,))

    def users(self):
        with self.db() as db:return [dict(x) for x in db.execute('SELECT id,email,name,enabled FROM users ORDER BY email')]
