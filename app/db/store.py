import sqlite3

from .auth import AuthStore
from .community import CommunityStore
from .debrids import DebridStore
from .runs import RunStore
from .settings import ConfigStore


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.auth = AuthStore(conn)
        self.config = ConfigStore(conn)
        self.debrid = DebridStore(conn)
        self.community = CommunityStore(conn)
        self.runs = RunStore(conn)
