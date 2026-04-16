from .diff import AddTableOp, DropTableOp, RebuildTableOp, AddColumnOp, AddIndexOp, DropIndexOp

def _render_index_lines(index_meta: dict, table_name: str) -> list[str]:
    cols_str = str(index_meta['columns']).replace("'", '"')
    return [f"    op.create_index('{index_meta['name']}', '{table_name}', {cols_str}, unique={index_meta['unique']})"]

def render_migration_code(ops: list, warnings: list) -> str:
    lines = []
    
    if warnings:
        lines.append('# [Auto-generated warning] =================================')
        for w in warnings:
            lines.append(f'# {w}')
        lines.append('# ======================================================\n')

    lines.append('from lite_orm.migr.operations import Op\n')
    lines.append('def upgrade(op: Op):')
    
    if not ops:
        lines.append('    pass # No structural changes detected.')
        return "\n".join(lines)

    for op_obj in ops:
        if isinstance(op_obj, AddTableOp):
            lines.append(f'    op.create_table("{op_obj.table}", [')
            for col_name, meta in op_obj.columns.items():
                opts = _build_opts_str(meta)
                lines.append(f'''        ('{col_name}', '{meta["type"]}', {{{opts}}}),''')
            lines.append('    ]')
            if op_obj.relation:
                lines.append(', relation=[')
                for fk in op_obj.relation:
                    lines.append(f'''        ('{fk["col"]}', '{fk["ref_table"]}', '{fk["ref_col"]}', '{fk["on_delete"]}'),''')
                lines.append('    ]')    
            lines.append(')')
            
            if op_obj.indexes:
                lines.append('')
                for idx_meta in op_obj.indexes:
                    lines.extend(_render_index_lines(idx_meta, op_obj.table))
            lines.append('')
            
        elif isinstance(op_obj, DropTableOp):
            lines.append(f'''    op.drop_table('{op_obj.table}')\n''')
            
        elif isinstance(op_obj, RebuildTableOp):
            lines.append(f'    # Structural changes or field deletions detected; using table reconstruction strategy: {op_obj.table}')
            lines.append(f'    op.rebuild_table("{op_obj.table}", [')
            for col_name, meta in op_obj.new_columns_def.items():
                opts = _build_opts_str(meta)
                lines.append(f'''        ('{col_name}', '{meta["type"]}', {{{opts}}}),''')
            lines.append('    ], copy_columns=[')
            for col in op_obj.copy_columns:
                lines.append(f'        "{col}",')
            lines.append('    ]')
            if op_obj.relation:
                lines.append(', relation=[')
                for fk in op_obj.relation:
                    lines.append(f'''        ('{fk["col"]}', '{fk["ref_table"]}', '{fk["ref_col"]}', '{fk["on_delete"]}'),''')
                lines.append('    ]')
            lines.append(')')
            
            if op_obj.indexes:
                lines.append('')
                for idx_meta in op_obj.indexes:
                    lines.extend(_render_index_lines(idx_meta, op_obj.table))
            lines.append('')
            
        elif isinstance(op_obj, AddColumnOp):
            lines.append(f'''    op.add_column('{op_obj.table}', '{op_obj.column}', '{op_obj.column_def["type"]}', {_build_kwargs_str(op_obj.column_def)})\n''')
            
        elif isinstance(op_obj, AddIndexOp):
            lines.extend(_render_index_lines({'name': op_obj.index_name, 'columns': op_obj.columns, 'unique': op_obj.unique}, op_obj.table))
            lines.append('')
            
        elif isinstance(op_obj, DropIndexOp):
            lines.append(f'    op.drop_index("{op_obj.index_name}")\n')

    return '\n'.join(lines)

def _build_opts_str(meta: dict) -> str:
    opts = []
    if meta.get('pk'): opts.append('"primary_key": True,')
    if meta.get('nullable') == False: opts.append('"nullable": False,')
    if meta.get('unique'): opts.append('"unique": True,')
    if meta.get('default') is not None: opts.append(f'"default": {repr(meta["default"])},')
    return ', '.join(opts)

def _build_kwargs_str(meta: dict) -> str:
    opts = []
    if meta.get('nullable') == False: opts.append('nullable=False')
    if meta.get('default') is not None: opts.append(f'default={repr(meta["default"])}')
    return ', '.join(opts) if opts else ''
