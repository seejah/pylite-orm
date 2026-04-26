from __future__ import annotations
import sqlite3, logging, threading
from typing import TypeVar, Type
from .conn import DbConn
from .model import DbModel
from .query import SelectBuilder, InsertBuilder, UpdateBuilder, DeleteBuilder   

logger = logging.getLogger(__name__)
T = TypeVar('T', bound='DbModel')

class DbSession:
    '''数据库会话类'''
    def __init__(self, db: DbConn):
        self.db = db

    def __enter__(self) -> DbSession:
        if not hasattr(self.db._local, 'session_count'):  self.db._local.session_count = 0
        self.db._local.session_count += 1
        conn = self._conn
        current_level = self.db._local._tx_level
        if current_level == 0:
            logger.info('Transaction BEGIN')
            conn.execute('BEGIN IMMEDIATE')
        else:
            conn.execute(f'SAVEPOINT sp_{current_level}')
            logger.debug("Savepoint sp_%s CREATED", current_level)
        self.db._local._tx_level += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        conn = self._conn
        self.db._local._tx_level -= 1
        current_level = self.db._local._tx_level
        if exc_type is not None:
            if current_level > 0: 
                conn.execute(f'ROLLBACK TO SAVEPOINT sp_{current_level}')
                logger.warning("Savepoint sp_%s ROLLBACK", current_level)
            else:
                conn.rollback()
                logger.error("Transaction ROLLBACK", exc_info=True)
        else:
            if current_level > 0: 
                conn.execute(f'RELEASE SAVEPOINT sp_{current_level}')
            else:
                conn.commit()
                logger.debug("Transaction COMMIT")
        self.db._local.session_count -= 1
        if self.db._local.session_count == 0:  self.db.close(silent=True)
        return False

    @property
    def _conn(self) -> sqlite3.Connection:
        return self.db.get_connection()

    def select(self, model_cls: Type[T]) -> SelectBuilder[T]:
        '''Select data operation'''
        return SelectBuilder(self, model_cls)

    def insert(self, model_cls: Type[T]) -> InsertBuilder[T]:
        '''Insert data operation'''
        return InsertBuilder(self, model_cls)

    def update(self, model_cls: Type[T]) -> UpdateBuilder[T]:
        '''Update data operation'''
        return UpdateBuilder(self, model_cls)

    def delete(self, model_cls: Type[T]) -> DeleteBuilder[T]:
        '''Delete data operation'''
        return DeleteBuilder(self, model_cls)

    def close(self):
        '''Close the current connection'''
        self.db.close()