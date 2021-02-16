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

    def associate_user_device(self, userid: int, mac: str):
        self._db.execute("INSERT INTO devices(mac, owner_userid) VALUES(?,?) ON CONFLICT(mac) DO UPDATE SET owner_userid=excluded.owner_userid", (mac, userid))
        self._db.commit()

    def get_user_by_email(self, email: str):
        results = self._query_db("SELECT email, userid, salt, password, mqtt_key FROM users WHERE email=?", (email,), one=True)
        return results

    def get_user_by_id(self, userid: int):
        results = self._query_db("SELECT email, userid, password, mqtt_key FROM users WHERE userid=?", (userid,), one=True)
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
