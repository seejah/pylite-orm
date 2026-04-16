from __future__ import annotations
import sqlite3, logging
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
        self._t_level = 0

    def __enter__(self) -> DbSession:
        conn = self._conn
        if self._t_level == 0:
            logger.info('Transaction BEGIN')
            conn.execute('BEGIN IMMEDIATE')
        else:
            conn.execute(f'SAVEPOINT sp_{self._t_level}')
            logger.debug("Savepoint sp_%s CREATED", self._t_level)
        self._t_level += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._t_level -= 1
        if exc_type is not None:
            if self._t_level > 0: 
                self._conn.execute(f'ROLLBACK TO SAVEPOINT sp_{self._t_level}')
                logger.warning("Savepoint sp_%s ROLLBACK", self._t_level)
            else:
                self._conn.rollback()
                logger.error("Transaction ROLLBACK", exc_info=True)
        else:
            if self._t_level > 0: 
                self._conn.execute(f'RELEASE SAVEPOINT sp_{self._t_level}')
            else:
                self._conn.commit()
                logger.debug("Transaction COMMIT")
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