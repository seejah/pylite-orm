import sqlite3
import importlib.util
import logging
from pathlib import Path

logger = logging.getLogger('pylite_orm.migr')

class MigrationRunner:
    def __init__(self, db_path: str, migrations_dir: str):
        self.db_path = db_path
        self.migrations_dir = Path(migrations_dir)
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(self.db_path, isolation_level=None)
        self.conn.execute('PRAGMA journal_mode=WAL;')
        self._ensure_migrations_table()

    def _ensure_migrations_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS _lite_migr (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def _get_applied_migrations(self) -> set[str]:
        cursor = self.conn.execute('SELECT name FROM _lite_migr')
        return {row[0] for row in cursor.fetchall()}

    def _get_pending_migrations(self) -> list[str]:
        applied = self._get_applied_migrations()
        all_files = sorted([f.stem for f in self.migrations_dir.glob('*.py') if not f.name.startswith('__')])
        return [f for f in all_files if f not in applied]

    def upgrade(self):
        pending = self._get_pending_migrations()
        if not pending:
            logger.info('The database is already up to date; no migration required')
            return

        logger.info(f'5 pending migrations found....')
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            for file_stem in pending:
                logger.info(f'Executing migration file: {file_stem}')
                module = self._load_migration_module(file_stem)
                
                from .operations import Op
                op = Op(self.conn)
                module.upgrade(op)
                
                self.conn.execute('INSERT INTO _lite_migr (name) VALUES (?)', (file_stem,))
                logger.info(f'Migration applied successfully: {file_stem}')
            self.conn.execute('COMMIT')
        except Exception as e:
            self.conn.execute('ROLLBACK')
            logger.error(f'Migration execution failed, rolled back: {e}', exc_info=True)
            raise
        finally:
            self.conn.close()

    def _load_migration_module(self, file_stem: str):
        file_path = self.migrations_dir / f'{file_stem}.py'
        try:
            spec = importlib.util.spec_from_file_location(file_stem, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception as e:
            logger.error(f'Failed to load migration {file_stem}: {e}')
            raise f'Migration {file_stem} is invalid: {e}'
