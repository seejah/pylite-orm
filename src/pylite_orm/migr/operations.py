import re, sqlite3

class Op:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @staticmethod
    def _safe_name(name: str, label: str = 'name'):
        if not re.match(r'^[a-zA-Z0-9_]+$', name):
            raise ValueError(f'Invalid {label}": "{name}"')
        return name

    def execute(self, sql: str, params=None):
        self.conn.execute(sql, params or [])

    def create_table(self, table_name: str, columns: list[tuple], relation: list[tuple] = None, if_not_exists: bool = True):
        table_name = self._safe_name(table_name, 'table_name')
        col_defs = []
        for col in columns:
            cname = self._safe_name(col[0], 'col_name')
            ctype = col[1] if len(col) > 1 else 'TEXT'
            options = col[2] if len(col) > 2 else {}
         
            parts = [f'{cname} {ctype}']
            if options.get('primary_key'): parts.append('PRIMARY KEY')
            if options.get('autoincrement'): parts.append('AUTOINCREMENT')
            if not options.get('nullable', True): parts.append('NOT NULL')
            if options.get('unique'): parts.append('UNIQUE')
            if 'default' in options: parts.append(f'DEFAULT {options["default"]}')
            col_defs.append(' '.join(parts))
        fk_defs = []
        if relation:
            for fk in relation:
                col, ref_tbl, ref_col, on_del = fk[0], fk[1], fk[2], fk[3] if len(fk) > 3 else 'NO ACTION'
                col = self._safe_name(col, 'fk_name')
                ref_tbl = self._safe_name(ref_tbl, 'ref_tbl_name')
                ref_col = self._safe_name(ref_col, 'ref_col_name')
                
                if on_del not in ('CASCADE', 'SET NULL', 'RESTRICT', 'NO ACTION'):
                    raise ValueError(f'Invalid ON DELETE strategy: {on_del}')
                if on_del == 'SET NULL':
                    for c in columns:
                        if c[0] == col and not c[2].get('nullable', True):
                            raise ValueError(f'Foreign key column "{col}" is set to ON DELETE SET NULL, but the column is not configured with nullable=True.')
                short_name = table_name.split('_')[-1]
                fk_name = f'fk_{short_name}_{col}_{ref_tbl}_{ref_col}'
                fk_defs.append(f'CONSTRAINT {fk_name} FOREIGN KEY ({col}) REFERENCES {ref_tbl}({ref_col}) ON DELETE {on_del}')
        all_defs = col_defs + fk_defs
        exists_sql = 'IF NOT EXISTS ' if if_not_exists else ''
        sql = f'CREATE TABLE {exists_sql}{table_name} ({", ".join(all_defs)})'
        self.conn.execute(sql)

    def drop_table(self, table_name: str, if_exists: bool = True):
        table_name = self._safe_name(table_name, 'table_name')
        exists_sql = 'IF EXISTS ' if if_exists else ''
        self.conn.execute(f'DROP TABLE {exists_sql}{table_name}')

    def add_column(self, table_name: str, column_name: str, col_type: str, **options):
        table_name = self._safe_name(table_name, 'table_name')
        column_name = self._safe_name(column_name, 'col_name')
        parts = [f'ALTER TABLE {table_name} ADD COLUMN {column_name} {col_type}']
        if not options.get('nullable', True): parts.append('NOT NULL')
        if options.get('default') is not None: parts.append(f'DEFAULT {options["default"]}')
        self.conn.execute(' '.join(parts))

    def rename_column(self, table_name: str, old_name: str, new_name: str):
        self.conn.execute(f'ALTER TABLE {self._safe_name(table_name)} RENAME COLUMN {self._safe_name(old_name)} TO {self._safe_name(new_name)}')

    def create_index(self, index_name: str, table_name: str, columns: list[str], unique: bool = False):
        idx = self._safe_name(index_name, 'idx_name')
        tbl = self._safe_name(table_name, 'table_name')
        cols = ', '.join([self._safe_name(c, 'col_name') for c in columns])
        u = 'UNIQUE ' if unique else ''
        self.conn.execute(f'CREATE {u}INDEX IF NOT EXISTS {idx} ON {tbl} ({cols})')

    def drop_index(self, index_name: str):
        self.conn.execute(f'DROP INDEX IF EXISTS {self._safe_name(index_name, "index_name")}')

    def rebuild_table(self, table_name: str, new_columns_def: list[tuple], copy_columns: list[str], relation: list[tuple] = None):
        tbl = self._safe_name(table_name, 'table_name')
        temp_tbl = f'_pylite_orm_temp_{tbl}'
        safe_copy_cols = ', '.join([self._safe_name(c) for c in copy_columns])
        self.create_table(temp_tbl, new_columns_def, relation=relation, if_not_exists=False)
        self.conn.execute(f'INSERT INTO {temp_tbl} ({safe_copy_cols}) SELECT {safe_copy_cols} FROM {tbl}')
        self.drop_table(tbl, if_exists=False)
        self.conn.execute(f'ALTER TABLE {temp_tbl} RENAME TO {tbl}')
