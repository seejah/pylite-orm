from __future__ import annotations
import sqlite3, threading, logging

class DbConn:
    ''' #### SQLite Database Connector
    - db_path: Database file path
    - return: Connection instance
    '''
    _ORM_LOGGER = "lite_orm" 

    def __init__(self, db_path: str, debug: bool = False):
        self.db_path = db_path
        self._local = threading.local()
        self._setup_logging(debug)

    def _setup_logging(self, debug: bool):
        orm_logger = logging.getLogger(self._ORM_LOGGER)
        
        if debug:
            orm_logger.setLevel(logging.DEBUG)
            if not orm_logger.handlers:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.DEBUG)
                console_handler.setFormatter(logging.Formatter('[LiteORM] %(message)s'))
                orm_logger.addHandler(console_handler)
        else:
            orm_logger.setLevel(logging.WARNING)
            orm_logger.handlers.clear()

    def get_connection(self) -> sqlite3.Connection:
        '''Get the current connection; create one if it doesn't exist'''
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            ver= sqlite3.sqlite_version
            logger = logging.getLogger(self._ORM_LOGGER)
            logger.info(f'New SQLite connection created for %s', threading.current_thread().name)
            logger.info(f'SQLite database version: {ver}')
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            conn.execute('PRAGMA journal_mode=WAL;')
            conn.execute('PRAGMA foreign_keys=ON;')
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def close(self):
        '''Close the current connection'''
        if hasattr(self._local, 'conn') and self._local.conn:
            try:     self._local.conn.close()
            except Exception as e:
                logging.getLogger(self._ORM_LOGGER).debug(f'Exception occurred while closing connection (usually can be ignored): {e}')
            finally: self._local.conn = None