import re
from typing import Any, Type, TYPE_CHECKING
if TYPE_CHECKING: from .model import DbModel

class Expr:
    def __init__(self, col: str, op: str, val: Any, escape: str|None=None, model_cls: Type['DbModel'] = None):
        self.col = col
        self.op = op
        self.val = val
        self.escape = escape
        self.model_cls = model_cls
    def __and__(self, other): return LogicNode('AND', self, other)
    def __or__(self, other):  return LogicNode('OR', self, other)
    def __invert__(self):     return LogicNode('NOT', self)
    def __bool__(self):       raise TypeError('The ORM data model does not support logical judgment')
    __hash__ = object.__hash__

class LogicNode:
    '''逻辑组合节点 (AND/OR/NOT)'''
    def __init__(self, op: str, left=None, right=None):
        self.op = op
        self.left = left
        self.right = right
    def __and__(self, other): return LogicNode('AND', self, other)
    def __or__(self, other):  return LogicNode('OR', self, other)   
    def __invert__(self):     return LogicNode('NOT', self)
    def __bool__(self):       raise TypeError("ORM 表达式不支持逻辑判断")

class Func:
    '''Field Function'''
    def __init__(self, func_col: str, alias: str|None = None):
        if '(' in func_col and ')' in func_col: pass
        elif not re.match(r'^[a-zA-Z0-9_.]+$', func_col):
            raise ValueError(f'Invalid function column name: {func_col}')
        self.func_col = func_col
        self._alias = alias

    def __str__(self) -> str:
        if self._alias:
            return f'{self.func_col} AS {self._alias}'
        return self.func_col
    
    def as_(self, alias: str) -> 'Func':
        if not re.match(r'^[a-zA-Z0-9_]+$', alias):  raise ValueError(f'Invalid alias: {alias}')
        return Func(self.func_col, alias)
    
    @staticmethod
    def count(col: str = '*') -> 'Func':
        if col != '*' and not re.match(r'^[a-zA-Z0-9_.]+$', col):
            raise ValueError(f"Func.count Invalid column name: {col}")
        return Func(f'COUNT({col})')

    @staticmethod
    def sum(col: str) -> 'Func':
        if not re.match(r'^[a-zA-Z0-9_.]+$', col): raise ValueError(f"Func.sum Invalid column name: {col}")
        return Func(f'SUM({col})')

    @staticmethod
    def max(col: str) -> 'Func':
        if not re.match(r'^[a-zA-Z0-9_.]+$', col): raise ValueError(f"Func.max Invalid column name: {col}")
        return Func(f'MAX({col})')

    @staticmethod
    def min(col: str) -> 'Func':
        if not re.match(r'^[a-zA-Z0-9_.]+$', col): raise ValueError(f"Func.min Invalid column name: {col}")
        return Func(f'MIN({col})')
    
    @staticmethod
    def date(col: str) -> 'Func':
        if not re.match(r'^[a-zA-Z0-9_.]+$', col): raise ValueError(f"Func.date Invalid column name: {col}")
        return Func(f"DATE({col})")

    @staticmethod
    def strftime(fmt: str, col: str) -> 'Func':
        if not re.match(r'^[a-zA-Z0-9_.]+$', col): raise ValueError(f"Func.strftime Invalid column name: {col}")
        if not re.match(r'^(?:%[a-zA-Z]|[\/\-\s:])+$', fmt):
            raise ValueError(f"Func.strftime Invalid format string: {fmt}")
        return Func(f"STRFTIME('{fmt}', {col})")