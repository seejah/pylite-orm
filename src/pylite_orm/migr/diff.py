from dataclasses import dataclass, field

@dataclass
class AddTableOp:
    table: str
    columns: dict
    indexes: list = field(default_factory=list)
    relation: list = field(default_factory=list)

@dataclass
class DropTableOp:
    table: str

@dataclass
class RebuildTableOp:
    table: str
    new_columns_def: dict
    copy_columns: list[str]
    indexes: list = field(default_factory=list)
    relation: list = field(default_factory=list)

@dataclass
class AddColumnOp:
    table: str
    column: str
    column_def: dict

@dataclass
class AddIndexOp:
    table: str
    index_name: str
    columns: list[str]
    unique: bool

@dataclass
class DropIndexOp:
    index_name: str

def calculate_diff(db_schema: dict, model_schema: dict) -> list:
    ops = []
    for table, t_def in model_schema.items():
        if table not in db_schema:
            ops.append(AddTableOp(table=table, columns=t_def['columns'], indexes=t_def.get('indexes', []), relation=t_def.get('relation', [])))
    for table in list(db_schema.keys()):
        if table not in model_schema:
            ops.append(DropTableOp(table=table))
    for table, m_def in model_schema.items():
        if table not in db_schema: continue
        db_cols = db_schema[table]['columns']
        m_cols = m_def['columns']
        need_rebuild = False
        add_cols = {}
        for col_name, col_meta in m_cols.items():
            if col_name not in db_cols:
                add_cols[col_name] = col_meta
            else:
                db_col_meta = db_cols[col_name]
                if (col_meta['type'] != db_col_meta['type'] or 
                    col_meta['nullable'] != db_col_meta['nullable'] or
                    col_meta['pk'] != db_col_meta['pk']):
                    need_rebuild = True
                    break
        for col_name in db_cols:
            if col_name not in m_cols:
                need_rebuild = True
                break
        db_indexes = {idx['name']: idx for idx in db_schema[table].get('indexes', [])}
        m_indexes = {idx['name']: idx for idx in m_def.get('indexes', [])}
        if set(db_indexes.keys()) != set(m_indexes.keys()):
            need_rebuild = True
        else:
            for idx_name in m_indexes:
                if (db_indexes[idx_name]['columns'] != m_indexes[idx_name]['columns'] or
                    db_indexes[idx_name]['unique'] != m_indexes[idx_name]['unique']):
                    need_rebuild = True
                    break
        db_relations = db_schema[table].get('relation', [])
        m_relations = m_def.get('relation', [])
        if len(db_relations) != len(m_relations):
            need_rebuild = True
        else:
            db_rel_set = {(rel['col'], rel['ref_table'], rel['ref_col'], rel['on_delete']) for rel in db_relations}
            m_rel_set  = {(rel['col'], rel['ref_table'], rel['ref_col'], rel['on_delete']) for rel in m_relations} 
            if db_rel_set != m_rel_set:
                need_rebuild = True
        if need_rebuild:
            copy_cols = [c for c in m_cols.keys() if c in db_cols]
            ops.append(RebuildTableOp(table=table, new_columns_def=m_cols, copy_columns=copy_cols, indexes=m_def.get('indexes', []), 
                relation=m_def.get('relation', [])))
        elif add_cols:
            for col_name, col_meta in add_cols.items():
                ops.append(AddColumnOp(table=table, column=col_name, column_def=col_meta))  
        if not need_rebuild:
            for idx_name, idx_meta in m_indexes.items():
                if idx_name not in db_indexes:
                    ops.append(AddIndexOp(table=table, index_name=idx_name, columns=idx_meta['columns'], unique=idx_meta['unique']))
            for idx_name in db_indexes:
                if idx_name not in m_indexes:
                    ops.append(DropIndexOp(index_name=idx_name))
    return ops