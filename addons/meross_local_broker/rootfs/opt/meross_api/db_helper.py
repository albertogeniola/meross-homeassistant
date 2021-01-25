import os
import sqlite3
from flask import g
from hashlib import sha256
from constants import _DB_PATH


class DbHelper:
    def __init__(self, path: str):
        self._db_path = path
        self._db = None

    def _init(self):
        self._db = sqlite3.connect(_DB_PATH)
        pass

    def _query_db(self, query, args=(), one=False):
        cur = self._db.execute(query, args)
        rv = cur.fetchall()
        cur.close()
        return (rv[0] if rv else None) if one else rv

    def store_new_user_token(self, userid, token):
        self._db.execute("INSERT INTO http_tokens(token, userid) VALUES(?,?)", (token, userid))
        self._db.commit()

    def get_user_by_email_password(self, email: str, password: str):
        hashed_pass = sha256()
        hashed_pass.update(password.encode('utf8'))
        hashed_pass.hexdigest()
        results = self._query_db("SELECT * FROM users WHERE email=? and password=?", (email, hashed_pass.hexdigest()), one=True)
        return results

    def close(self):
        self._db.close()
        delattr(g, '_database')

    @classmethod
    def get_db(cls, path: str = _DB_PATH) -> 'DbHelper':
        db = getattr(g, '_database', None)
        if db is None:
            db = DbHelper(path)
            db._init()
            g._database = db
        return db
