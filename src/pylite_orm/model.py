import re
from typing import Any, Iterable, Callable, TypeVar
from .expr import Expr

T = TypeVar('T', bound='DbModel')
_MISSING = object()

class Field:
    def __init__(self, *, db_column=None, db_type=None, nullable=True, pk=False, default=_MISSING, default_factory=None,
                 init=True, repr=True, **extra_meta):
        self.metadata = {'db_column':db_column, 'db_type':db_type, 'nullable':nullable, 'pk':pk, **extra_meta}
        self.default = default
        self.default_factory = default_factory
        self.init = init
        self.repr = repr
        self.name = None
        self.owner = None

    def __get__(self, obj: Any, objtype: Any = None) -> 'Field | Any':
        if obj is None:  return self
        return obj.__dict__.get(self.name)

    def __set__(self, obj: Any, value: Any) -> None:
        if not hasattr(obj, '_dirty_fields'):
            obj._dirty_fields = set()
        old_val = obj.__dict__.get(self.name, _MISSING)
        if old_val is _MISSING or old_val != value:  obj._dirty_fields.add(self.name)
        obj.__dict__[self.name] = value

    def __eq__(self, val: Any) -> 'Expr': 
        if val is None: return Expr(self.name, 'IS NULL', None, model_cls=self.owner)
        return Expr(self.name, '=', val, model_cls=self.owner)
    
    def __ne__(self, val: Any) -> 'Expr':
        if val is None: return Expr(self.name, 'IS NOT NULL', None, model_cls=self.owner)
        return Expr(self.name, '!=', val, model_cls=self.owner)
    
    def __gt__(self, val: Any) -> 'Expr': return Expr(self.name, '>', val, model_cls=self.owner)
    def __ge__(self, val: Any) -> 'Expr': return Expr(self.name, '>=', val, model_cls=self.owner)
    def __lt__(self, val: Any) -> 'Expr': return Expr(self.name, '<', val, model_cls=self.owner)
    def __le__(self, val: Any) -> 'Expr': return Expr(self.name, '<=', val, model_cls=self.owner)
    def __bool__(self):  raise TypeError('The ORM data model does not support logical judgment')

    __hash__ = object.__hash__

    def in_(self, val_list: Iterable[Any]) -> 'Expr':   return Expr(self.name, 'IN', list(val_list))
    def like(self, pattern: str) -> 'Expr':  return Expr(self.name, 'LIKE', pattern)
    
    def contains(self, val: str) -> 'Expr':
        escaped = val.replace('%', '/%').replace('_', '/_')
        return Expr(self.name, 'LIKE', f'%{escaped}%', '/')
    
    def startswith(self, val: str) -> 'Expr':
        escaped = val.replace('%', '/%').replace('_', '/_')
        return Expr(self.name, 'LIKE', f'{escaped}%', '/')
    
    def endswith(self, val: str) -> 'Expr':
        escaped = val.replace('%', '/%').replace('_', '/_')
        return Expr(self.name, 'LIKE', f'%{escaped}', '/')


class DbType:
    '''Database Field Type'''
    TEXT = 'TEXT'
    INT = 'INTEGER'
    REAL = 'REAL'
    BLOB = 'BLOB'


class RelType:
    '''Relationship Type'''
    O2O = 'O2O'
    O2M = 'O2M'
    M2O = 'M2O'


class OnDelete:
    '''On Delete Action'''
    RESTRICT = 'RESTRICT'
    CASCADE = 'CASCADE'
    SET_NULL = 'SET NULL'
    SET_DEFAULT = 'SET DEFAULT'
    NO_ACTION = 'NO ACTION'


class DbModel:
    '''Database Model Class'''
    _REGISTRY = {}

    class Meta:
        table: str = None
        indexes: list = []
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        DbModel._REGISTRY[cls.__name__] = cls
        cls_fields = {}
        for kls in reversed(cls.__mro__):
            for name, value in list(vars(kls).items()):
                if isinstance(value, Field) and name not in cls_fields:
                    value.name = name
                    value.owner = cls
                    cls_fields[name] = value
                    if hasattr(cls, '__annotations__') and name in cls.__annotations__:
                        value.metadata['type_hint'] = cls.__annotations__[name]
        cls.__model_fields__ = cls_fields

    def __init__(self, **kwargs):
        for f_name, f in self.__model_fields__.items():
            if f.metadata.get('virtual'): continue
            if not f.init: continue
            if f_name in kwargs:                self.__dict__[f_name] = kwargs[f_name]
            elif f.default is not _MISSING:     self.__dict__[f_name] = f.default
            elif f.default_factory is not None: self.__dict__[f_name] = f.default_factory()
            else:                               self.__dict__[f_name] = None
   
    def __repr__(self):
        parts = []
        for f_name, f in self.__model_fields__.items():
            if f.metadata.get('virtual'): 
                if f.metadata.get('relation') and f_name in self.__dict__:
                    value = self.__dict__[f_name]
                    parts.append(f"{f_name}={value!r}")
                continue
            if f_name == '__tablename__': continue
            if not f.repr: continue
            value = self.__dict__.get(f_name)
            parts.append(f"{f_name}={value!r}")
        return f"{self.__class__.__name__}({', '.join(parts)})"

    @classmethod
    def table_name(cls) -> str:
        '''Table name corresponding to the data model'''
        if hasattr(cls, 'Meta') and cls.Meta.table:
            return cls.Meta.table
        return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', cls.__name__).lower()
    
    @classmethod
    def get_pk_name(cls) -> str:
        for name, f in cls.__model_fields__.items():
            if f.metadata.get('pk'): return name
        return 'id'

    def asdict(self, exc_unset: bool = False):
        '''Convert the model instance to a dictionary'''
        if not exc_unset:  return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        dirty_fields = getattr(self, '_dirty_fields', None)
        if not dirty_fields:
            return {}
        valid_keys = self.__model_fields__.keys()
        return {
            k: self.__dict__[k] 
            for k in dirty_fields if k in valid_keys and k in self.__dict__
        }

def DbField(db_column: str|None = None, db_type: str|None = None, nullable: bool = True, pk: bool = False, 
            default: Any = _MISSING, default_factory: Callable|None = None, relation: str|None = None, on_delete: str|None = None)  -> Field:
    ''' Field attribute options'''
    return Field(db_column=db_column, db_type=db_type, nullable=nullable, pk=pk, default=default,
                 default_factory=default_factory, relation=relation, on_delete=on_delete, init=True, repr=True)


def RelationField(fk: str|None = None) -> Field:
    ''' Field attribute options'''
    return Field(init=False, repr=False, virtual=True, relation=True, fk=fk)
