import sqlite3, importlib.util, sys, logging
from pathlib import Path

logger = logging.getLogger(__name__)

TYPE_FALLBACK_MAP = {
    'int':'INTEGER', 'str':'TEXT', 'float':'REAL', 'bool':'INTEGER', 'bytes': 'BLOB'}

def get_db_schema(conn: sqlite3.Connection) -> dict[str, dict]:
    schema = {}
    cursor = conn.execute('SELECT name FROM sqlite_master WHERE type="table" AND name NOT LIKE "sqlite_%" AND name != "_lite_migr"')
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in tables:
        schema[table] = {'columns': {}, 'indexes': [], 'relation': []}
        cols_cursor = conn.execute(f'PRAGMA table_info("{table}")')
        for row in cols_cursor.fetchall():
            cid, name, dtype, notnull, dflt_value, pk = row
            schema[table]['columns'][name] = {
                'type': dtype.upper() if dtype else 'TEXT',
                'nullable': not notnull == 1,
                'pk': bool(pk),
                'default': dflt_value
            }
        idx_cursor = conn.execute(f'PRAGMA index_list("{table}")')
        for row in idx_cursor.fetchall():
            idx_name, unique, origin = row[1], row[2], row[3]
            if origin == 'pk': continue
            cols_idx_cursor = conn.execute(f'PRAGMA index_info("{idx_name}")')
            idx_cols = [r[2] for r in cols_idx_cursor.fetchall()]
            schema[table]['indexes'].append({'name': idx_name, 'columns': idx_cols, 'unique': bool(unique)})
        fk_cursor = conn.execute(f'PRAGMA foreign_key_list("{table}")')
        for row in fk_cursor.fetchall():
            id, seq, table_name, from_col, to_col, on_update, on_delete, match = row
            schema[table]['relation'].append({
                'col': from_col,
                'ref_table': table_name,
                'ref_col': to_col,
                'on_delete': on_delete
            })
    return schema

def get_model_schema(models_dir: str) -> dict[str, dict]:
    models_path = Path(models_dir).resolve()
    if not models_path.exists(): raise FileNotFoundError(f'The configured model directory does not exist: {models_path}')
    str_path = str(models_path.parent)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)

    for py_file in models_path.glob('*.py'):
        if py_file.name.startswith('__'): continue
        module_name = py_file.stem
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f'Failed to import model file {py_file}: {e}')
            raise

    from ..model import DbModel
    schema = {}
    missing_type_warnings = []

    for _, cls in DbModel._REGISTRY.items():
        table_name = cls.table_name()
        table_def = {'columns': {}, 'indexes': [], 'relation': []}
        for field_name, field in cls.__model_fields__.items():
            meta = field.metadata
            if meta.get('virtual'): continue
            db_type = meta.get('db_type')
            if not db_type:
                hint = meta.get('type_hint')
                db_type = TYPE_FALLBACK_MAP.get(str(hint) if hint else "", "TEXT")
                if db_type == "TEXT": missing_type_warnings.append(f"  - {table_name}.{field_name}")
            table_def['columns'][field_name] = {
                'type': db_type.upper(),
                'nullable': meta.get('nullable', True),
                'pk': meta.get('pk', False),
                'default': meta.get('default') if meta.get('default') is not None else None
            }
            fk_target = meta.get('relation')
            if fk_target:
                if '.' not in fk_target:
                    raise ValueError(f'Foreign key format error: "{fk_target}"，should be "table.column" (like "users.id")')
                target_table, target_col = fk_target.split('.')
                on_delete = (meta.get('on_delete') or 'NO ACTION').upper()
                if on_delete not in ('CASCADE', 'SET NULL', 'RESTRICT', 'NO ACTION'):
                    raise ValueError(f'Unsupported on_delete strategy: "{on_delete}"')
                
                table_def['relation'].append({
                    'col': field_name,
                    'ref_table': target_table,
                    'ref_col': target_col,
                    'on_delete': on_delete
                })
        indexes = getattr(cls.Meta, 'indexes', []) if hasattr(cls, 'Meta') else []
        for idx_def in indexes:
            if isinstance(idx_def, str):
                if idx_def in table_def['columns'] and not table_def['columns'][idx_def].get('pk'):
                    table_def['indexes'].append({
                        'name': f'idx_{table_name}_{idx_def}',
                        'columns': [idx_def],
                        'unique': False
                    })
            elif isinstance(idx_def, (tuple, list)):
                idx_name = f'idx_{table_name}_{"_".join(idx_def)}'
                table_def['indexes'].append({
                    'name': idx_name,
                    'columns': list(idx_def),
                    'unique': False
                })
        schema[table_name] = table_def
    if missing_type_warnings:
        logger.warning('Some fields are detected without explicitly declared db_type; TEXT is used by default:\n' + '\n'.join(missing_type_warnings))
    return schema