from __future__ import annotations
import re, logging
from typing import Type, Any, Union, Generic, TypeVar, Self, TYPE_CHECKING, get_origin, get_args
if TYPE_CHECKING: from .session import DbSession
from .model import DbModel, RelType, Field
from .expr import Expr, LogicNode, Func

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=DbModel)

O = TypeVar('O')

class AttrDict(dict):
    def __getattr__(self, key):
        try: return self[key]
        except KeyError: raise AttributeError(f'AttrDict object has no attribute "{key}"')
    def __setattr__(self, key, value): self[key] = value

class JoinType():
    INNER = 'INNER'
    LEFT = 'LEFT'
    RIGHT = 'RIGHT'


class BaseBuilder(Generic[T]):
    _VALID = re.compile(r'^[a-zA-Z0-9_]+$')
    def __init__(self, session: DbSession, model_cls: Type[T]):
        self._session = session
        self._model_cls = model_cls
        self._where_clauses: list[str] = []
        self._where_params: list[Any] = []

    @staticmethod
    def _compile(node: Union['Expr', 'LogicNode'], model_cls: Type['DbModel'] = None) -> tuple[str, list]:
        if isinstance(node, Expr):
            col, op, val = node.col, node.op, node.val
            current_model_cls = node.model_cls or model_cls
            if '.' not in col and current_model_cls:
                if col in current_model_cls.__model_fields__:
                    col = f'{current_model_cls.table_name()}.{col}'
            if isinstance(val, Field):
                right_col = val.name
                if val.owner:  right_col = f'{val.owner.table_name()}.{right_col}'
                return f'{col} {op} {right_col}', []
            if op == 'LIKE' and node.escape:
                return f'{col} {op} ? ESCAPE ?', [val, node.escape]
            if op in ('IS NULL', 'IS NOT NULL'):
                return f"{col} {op}", []
            if op == 'IN':
                if not isinstance(val, (list, tuple)): raise ValueError('IN operation requires a list')
                if not val: return '1=0', []
                ph = ', '.join(['?'] * len(val))
                return f'{col} IN ({ph})', list(val)
            return f'{col} {op} ?', [val]
        elif isinstance(node, LogicNode):
            if node.op == 'NOT':
                sql, params = BaseBuilder._compile(node.left, model_cls)
                return f'NOT ({sql})', params
            l_sql, l_params = BaseBuilder._compile(node.left, model_cls)
            r_sql, r_params = BaseBuilder._compile(node.right, model_cls)
            return f'({l_sql} {node.op} {r_sql})', l_params + r_params
        else:
            raise TypeError(f'filter() Direct {type(node)} passing is not supported, please use the format User.name == "xxx"')

    def filter(self, *nodes: Union['Expr', 'LogicNode']) -> Self:
        '''Conditional query'''
        if not nodes: return self
        combined = nodes[0]
        for n in nodes[1:]:
            combined = combined & n
        sql, params = self._compile(combined, self._model_cls)
        self._where_clauses.append(f'({sql})')
        self._where_params.extend(params)
        return self

    def where(self, clause: str, *args: Any) -> Self:
        '''Native SQL where clause'''
        self._where_clauses.append(f'({clause})')
        self._where_params.extend(args)
        return self

    def _build_where(self) -> tuple[str, list]:
        if not self._where_clauses: return '', []
        return ' WHERE ' + ' AND '.join(self._where_clauses), self._where_params


class SelectBuilder(BaseBuilder[T]):
    _VALID_ORDERBY = re.compile(r'^(?:-?[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)$')
    def __init__(self, session: DbSession, model_cls: Type[T]):
        super().__init__(session, model_cls)
        self._order_sql = ''
        self._limit_val = 0
        self._offset_val = 0
        self._group_by = []
        self._joins = []
        self._preloads: set[str] = set()
        self._custom_select: str | None = None
        self._col_mapping: dict[str, str] = {}
        self._join_params: list[Any] = []
   
    def join(self, target_model: Type['DbModel'], on: Expr, join_type:JoinType = JoinType.LEFT) -> 'SelectBuilder[T]':
        '''Join statement'''
        table = target_model.table_name()
        if not self._VALID.match(table): raise ValueError(f'Invalid table name: {table}')
        on_sql, on_params = self._compile(on, self._model_cls)
        self._joins.append(f'{join_type} JOIN {table} ON {on_sql}')
        self._join_params.extend(on_params)
        return self        

    def columns(self, *columns: str | Func)  -> 'SelectBuilder[T]':
        '''Specify custom query columns (used with join, supports Func)'''
        parts = []
        self._col_mapping = {}  # 重置映射
        for col in columns:
            if isinstance(col, Func):
                func_str = str(col)
                parts.append(func_str)
                alias = col._alias or func_str
                self._col_mapping[alias] = func_str
            elif isinstance(col, str):
                if re.match(r'^.+\s+AS\s+.+$', col, re.IGNORECASE):
                    match = re.match(r'^.+\s+AS\s+([a-zA-Z0-9_]+)$', col, re.IGNORECASE)
                    alias = match.group(1) if match else col
                    parts.append(col)
                    self._col_mapping[alias] = col
                elif '.' in col:
                    table, column = col.split('.', 1)
                    alias = f'{table}__{column}'
                    parts.append(f'{col} AS {alias}')
                    self._col_mapping[alias] = col
                else:
                    parts.append(col)
                    self._col_mapping[col] = col
            else:  
                raise TypeError('select_columns Only strings or Func objects are supported')
        self._custom_select = ', '.join(parts)
        return self

    def order_by(self, *columns: str) -> 'SelectBuilder[T]':
        '''Order by columns'''
        parts = []
        for col in columns:
            if not self._VALID_ORDERBY.match(col): raise ValueError(f'Invalid sort column name: {col}')
            parts.append(f'{col[1:]} DESC' if col.startswith('-') else f'{col} ASC')
        self._order_sql = 'ORDER BY ' + ', '.join(parts)
        return self

    def group_by(self, *columns: str | Func) -> 'SelectBuilder[T]':
        '''Group by columns'''
        self._group_by.extend([str(col) for col in columns])
        return self

    def limit(self, count: int, offset: int = 0) -> 'SelectBuilder[T]':
        '''Limit the number of records returned'''
        self._limit_val = int(count); self._offset_val = int(offset); return self

    def _parse_row_to_nested(self, row_dict: dict) -> dict:
        if not self._col_mapping:
            return row_dict
        result = {}
        for alias, original in self._col_mapping.items():
            value = row_dict.get(alias)
            if '__' in alias:
                table, col = alias.split('__', 1)
                if table not in result:
                    result[table] = {}
                result[table][col] = value
            else:
                result[alias] = value
        return result

    def preload(self, *relations: str) -> 'SelectBuilder[T]':
        '''Preloaded associated tables (data model)'''
        self._preloads.update(relations)
        return self

    def _build(self, select_override: str|None = None) -> tuple[str, list]:
        table = self._model_cls.table_name()
        if not self._VALID.match(table): raise ValueError(f'Invalid table name: {table}')
        select_part = select_override or self._custom_select
        if not select_part:
            valid_cols = [name for name, field in self._model_cls.__model_fields__.items() if not field.metadata.get('virtual')]
            select_part = ', '.join(valid_cols) if valid_cols else '*'

        sql = f'SELECT {select_part} FROM {table}'
        if self._joins:    sql += ' ' + ' '.join(self._joins)
        w_sql, w_params = self._build_where()
        if w_sql:          sql += f' {w_sql}'
        if self._group_by: sql += f' GROUP BY {", ".join(self._group_by)}'
        if self._order_sql:sql += f' {self._order_sql}'
        if self._limit_val:sql += f' LIMIT {self._limit_val} OFFSET {self._offset_val}'
        return sql, self._join_params + w_params
    
    def _execute_preloads(self, instances: list[T], asdict: bool = False):
        if not instances or not self._preloads: return
        pk_name = self._model_cls.get_pk_name()
        pks = [inst.__dict__[pk_name] for inst in instances if inst.__dict__.get(pk_name) is not None]
        if not pks: return
        def _resolve_type(hint):
            if not isinstance(hint, str):
                origin = get_origin(hint)
                args = get_args(hint)
                if origin is list:
                    if args and hasattr(args[0], '__name__'):  return True, args[0].__name__
                    return True, str(args[0]) if args else None
                if hasattr(hint, '__name__'):  return False, hint.__name__
                return False, str(hint)
            hint_str = hint.strip()
            if (hint_str.startswith('list[') or hint_str.startswith('List[')) and hint_str.endswith(']'):
                inner_str = hint_str[5:-1].strip()
                return True, inner_str
            return False, hint_str
        for rel_name in self._preloads:
            f_info = self._model_cls.__model_fields__.get(rel_name)
            if f_info is None or not f_info.metadata.get('relation'): continue
            type_hint = f_info.metadata.get('type_hint')
            if not type_hint:  
                raise ValueError(f'''Preload '{rel_name}' failed: missing type hint, please use format `{rel_name}: list[TargetModel] = RelationField()`''')
            is_list, target_model_name = _resolve_type(type_hint)
            rel_type = RelType.O2M if is_list else RelType.M2O
            if not target_model_name:  raise ValueError(f"Preload '{rel_name}' failed: cannot extract target model name...")
            target_cls = DbModel._REGISTRY.get(target_model_name)
            if not target_cls: raise ValueError(f'''Preload '{rel_name}' failed: associated model '{target_model_name}' not registered, please check type hint of '{rel_name}''')
            fk = f_info.metadata.get('fk')
            if not fk: raise ValueError(f'''Preload '{rel_name}' failed: missing foreign key configuration (fk=...)''')
            target_cols = [n for n, f in target_cls.__model_fields__.items() if not f.metadata.get('virtual')]
            select_str = ', '.join(target_cols)
            if rel_type == RelType.O2M:
                ph = ', '.join(['?'] * len(pks))
                sql = f'SELECT {select_str} FROM {target_cls.table_name()} WHERE {fk} IN ({ph})'
                logger.debug('%s | Params: %s', sql, pks)
                cursor = self._session._conn.execute(sql, pks)
                target_instances = []
                for row in cursor.fetchall():
                    if asdict:
                        target_instances.append(dict(row))
                    else:
                        inst = target_cls.__new__(target_cls)
                        inst.__dict__ = dict(row)
                        target_instances.append(inst)
                grouped = {}
                for t_inst in target_instances:
                    fk_val = t_inst[fk] if isinstance(t_inst, dict) else getattr(t_inst, fk)
                    grouped.setdefault(fk_val, []).append(t_inst)                
                for inst in instances:
                     inst.__dict__[rel_name] = grouped.get(getattr(inst, pk_name), [])
            else:
                fks = list({getattr(inst, fk) for inst in instances if getattr(inst, fk, None) is not None})
                if not fks: continue
                target_pk_name = target_cls.get_pk_name()
                ph = ', '.join(['?'] * len(fks))
                sql = f'SELECT {select_str} FROM {target_cls.table_name()} WHERE {target_pk_name} IN ({ph})'
                logger.debug('%s | Params: %s', sql, fks)
                cursor = self._session._conn.execute(sql, fks)
                target_instances = []
                for row in cursor.fetchall():
                    if asdict:
                        target_instances.append(dict(row))
                    else:
                        inst = target_cls.__new__(target_cls)
                        inst.__dict__ = dict(row)
                        target_instances.append(inst)
                indexed = {}
                for t_inst in target_instances:
                    pk_val = t_inst[target_pk_name] if isinstance(t_inst, dict) else getattr(t_inst, target_pk_name)
                    indexed[pk_val] = t_inst                    
                for inst in instances:
                    inst.__dict__[rel_name] = indexed.get(getattr(inst, fk))

    def all(self) -> list[T]:
        '''Return all records as a list of instances'''
        sql, params = self._build()
        logger.debug('%s | Params: %s', sql, params)
        try:
            cursor = self._session._conn.execute(sql, params)
            results = []
            for row in cursor.fetchall():
                inst = self._model_cls.__new__(self._model_cls)
                inst.__dict__ = dict(row)
                results.append(inst)
            self._execute_preloads(results)
            return results
        except Exception as e:
            logger.error("SELECT Failed: %s | SQL: %s | Params: %s", e, sql, params, exc_info=True)
            raise

    def iter(self):
        '''Return an iterator of instances'''
        if self._preloads:
            raise ValueError('iter() does not support preload(). For large datasets, please use join() instead to perform table join queries at the SQL layer')        
        sql, params = self._build()
        logger.debug('%s | Params: %s', sql, params)
        try:
            cursor = self._session._conn.execute(sql, params)
            for row in cursor:
                inst = self._model_cls.__new__(self._model_cls)
                inst.__dict__ = dict(row)
                yield inst
        except Exception as e:
            logger.error("ITER Failed: %s | SQL: %s | Params: %s", e, sql, params, exc_info=True)
            raise

    def serial(self, O: Type[O] = None) -> AttrDict | O | None:
        '''Return the first record as a dictionary or instance'''
        results = self.limit(1).serial_list(O)
        return results[0] if results else None

    def serial_list(self, O: Type[O] = None) -> list[AttrDict] | list[O]:
        '''Return all records as a list of dictionaries or instances'''
        sql, params = self._build()
        logger.debug('%s | Params: %s', sql, params) 
        try:
            cursor = self._session._conn.execute(sql, params)
            if self._custom_select:
                rows = cursor.fetchall()
                serial = [AttrDict(self._parse_row_to_nested(dict(row))) for row in rows]
            else:
                instances = []
                for row in cursor.fetchall():
                    inst = self._model_cls.__new__(self._model_cls)
                    inst.__dict__ = dict(row)
                    instances.append(inst)
                self._execute_preloads(instances, asdict=True)
                serial = [AttrDict(inst.__dict__) for inst in instances]
            if O: serial = [O(**s) for s in serial]
            return serial
        except Exception as e:
            logger.error('SELECT Failed: %s | SQL: %s | Params: %s', e, sql, params, exc_info=True)
            raise

    def first(self) -> T | None:
        '''Return the first record as an instance'''
        results = self.limit(1).all(); return results[0] if results else None

    def count(self) -> int:
        '''Return the count of records'''
        sql, params = self._build()
        if self._group_by:
            sql = f'SELECT COUNT(*) as cnt FROM ({sql}) as _subq'
        else:
            from_index = sql.upper().find(' FROM ')
            if from_index != -1:  sql = 'SELECT COUNT(*) as cnt' + sql[from_index:]
        logger.debug('%s | Params: %s', sql, params)
        try:
            return self._session._conn.execute(sql, params).fetchone()['cnt']
        except Exception as e:
            logger.error('COUNT Failed: %s | SQL: %s | Params: %s', e, sql, params, exc_info=True)
            raise
        
    def value(self, column: str | Func) -> Any | None:
        '''Return the first value of a column'''
        safe_str = str(column) if isinstance(column, Func) else column
        if isinstance(column, str) and not self._VALID.match(safe_str):  raise ValueError(f'Invalid column name "{safe_str}"')
        sql, params = self._build(select_override=safe_str)
        if 'LIMIT' not in sql.upper(): sql += ' LIMIT 1'
        logger.debug('%s | Params: %s', sql, params)
        try:
            row = self._session._conn.execute(sql, params).fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.error('VALUE Failed: %s', e, exc_info=True)
            raise

    def values(self, *columns: str | Func) -> list[Any] | list[tuple]:
        '''Return all values of columns'''
        safe_cols = []
        for col in columns:
            if isinstance(col, Func):  safe_cols.append(str(col))
            elif isinstance(col, str):
                if not self._VALID.match(col): raise ValueError(f'Invalid column name "{col}"')
                safe_cols.append(col)
        select_part = ', '.join(safe_cols)
        sql, params = self._build(select_override=select_part)
        logger.debug('%s | Params: %s', sql, params)
        try:
            cursor = self._session._conn.execute(sql, params)
            rows = cursor.fetchall()
            if not rows: return []
            if len(safe_cols) == 1: result = [row[0] for row in rows]
            else:                   result =  [tuple(row) for row in rows]
            if len(result) == 1 and isinstance(result[0], tuple): result = list(result[0])
            return result
        except Exception as e:
            logger.error("VALUES Failed: %s", e, exc_info=True)
            raise


class InsertBuilder(Generic[T]):
    _VALID = re.compile(r'^[a-zA-Z0-9_]+$')
    def __init__(self, session: DbSession, model_cls: Type[T]):
        self._session = session
        self._model_cls = model_cls
        self._items: list = []

    def item(self, data: Union[T, dict, list[T], list[dict]]) -> 'InsertBuilder[T]':
        '''Add an item to the insert builder'''
        if isinstance(data, list): self._items.extend(data)
        else:                      self._items.append(data)
        return self
    
    def exec(self) -> int:
        '''Execute the insert operation'''
        if not self._items: return 0
        table = self._model_cls.table_name()
        if not self._VALID.match(table): raise ValueError(f'Invalid table name: "{table}"')
        valid_keys = set(self._model_cls.__model_fields__.keys())
        pk_name = self._model_cls.get_pk_name()
        processed_data = []
        for item in self._items:
            if isinstance(item, dict):
                item_dict = {
                    k: v for k, v in item.items() 
                    if k in valid_keys and not (k == pk_name and v is None)
                }
                processed_data.append(item_dict)
            elif isinstance(item, self._model_cls):
                item_dict = {
                    k: v for k, v in item.__dict__.items() 
                    if k in valid_keys and not (k == pk_name and v is None)
                }
                processed_data.append(item_dict)
            else:
                raise TypeError(
                    f'Unsupported data type: {type(item).__name__}，'
                    f'Expecting {self._model_cls.__name__} instance or dict'
                )
        if not processed_data:
            return 0
        for key in processed_data[0].keys():
            if not self._VALID.match(key): raise ValueError(f'Invalid column name "{key}"')
        keys = ', '.join(processed_data[0].keys())
        placeholders = ', '.join([f':{k}' for k in processed_data[0].keys()])
        sql = f'INSERT INTO {table} ({keys}) VALUES ({placeholders})'
        logger.debug('%s | Items: %d', sql, len(self._items))
        try:
            if len(processed_data) == 1:
                cursor = self._session._conn.execute(sql, processed_data[0])
                return cursor.lastrowid
            else:
                self._session._conn.executemany(sql, processed_data)
                return len(self._items)
        except Exception as e:
            logger.error("INSERT Failed: %s | SQL: %s", e, sql, exc_info=True)
            raise


class UpdateBuilder(BaseBuilder[T]):
    def __init__(self, session: DbSession, model_cls: Type[T]):
        super().__init__(session, model_cls)
        self._set_clause = ''
        self._set_params: list[Any] = []

    def item(self, data:dict|None=None, **kwargs) -> 'UpdateBuilder[T]':
        '''Add an item to the update builder'''
        merged = {**(data or {}), **kwargs}       
        if not merged:  raise ValueError('Update operation must provide fields to update')
        parts, params = [], []
        for k, v in merged.items():
            if not self._VALID.match(k): raise ValueError(f'Invalid column name "{k}"')
            parts.append(f'{k} = ? ')
            params.append(v)
        self._set_clause = 'SET ' + ', '.join(parts)
        self._set_params = params
        return self

    def exec(self) -> int:
        '''Execute the update operation'''
        if not self._set_clause: raise ValueError('Update operation must call .set() first')
        sql = f'UPDATE {self._model_cls.table_name()} {self._set_clause}'
        w_sql, w_params = self._build_where()
        if w_sql: sql += f'{w_sql}'
        final_params = self._set_params + w_params
        if not self._where_clauses:
            logger.warning("DANGEROUS: Executing UPDATE without WHERE clause! Table: %s", self._model_cls.table_name())       
        logger.debug('%s | Params: %s', sql, final_params)  ## NOTE 观测点
        try:
            return self._session._conn.execute(sql, final_params).rowcount
        except Exception as e:
            logger.error("UPDATE Failed: %s | SQL: %s", e, sql, exc_info=True)
            raise   


class DeleteBuilder(BaseBuilder[T]):
    def exec(self) -> int:
        '''Execute the delete operation'''
        sql = f'DELETE FROM {self._model_cls.table_name()}'
        w_sql, w_params = self._build_where()
        if w_sql: sql += f'{w_sql}'
        logger.debug('%s | Params: %s', sql, w_params)
        try:
            return self._session._conn.execute(sql, w_params).rowcount
        except Exception as e:
            logger.error('DELETE Failed: %s | SQL: %s', e, sql, exc_info=True)
            raise