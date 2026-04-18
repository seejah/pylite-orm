# pylite-orm

🌍 **Languages**: **English** | [中文](README.cn.md)

---

pylite-orm is a relatively new lightweight SQLite ORM tool based on Python. It provides developers with a concise and intuitive interface for SQLite operations.

In the context of many excellent Python ORM frameworks already existing (such as SQLAlchemy, Tortoise-ORM, Peewee), why use pylite-orm?

Obviously, in some specific scenarios, such as desktop software, mobile applications, embedded systems, and script development, SQLite is usually used as a single-file database. In these cases, using the aforementioned ORMs seems heavy, while PyLite-ORM provides a simpler API and smaller memory footprint—it only has a few simple syntaxes and is only 40K in size! This is the meaning of pyLite-orm's existence.

Features of pylite-orm:

- Simple and easy to use, quick to get started
- Small codebase, low memory usage
- Support for transactions
- Support for multiple database connections
- Support for multi-table queries and relationships (one-to-one, one-to-many)
- Support for native SQL queries
- Support for populating query results into Python objects, lists, dictionaries, and the most popular Pydantic models, etc.
- Built-in data migration tool, production-ready

If you are familiar with SQLAlchemy, Peewee, or other popular Python ORM frameworks, you can immediately start using PyLite-ORM.

## 1 Install pylite-orm

```bash
pip install pylite-orm
```

## 2 Getting Started Examples

### 2.1 Define Data Model

```python
from pylite_orm import  DbModel, DbField, DbType
from datetime import datetime

class User(Model):
    id = DbField(db_type=DbType.INT, pk=True)
    name = DbField(db_type=DbType.TEXT)
    age = DbField(db_type=DbType.INT)
    created_at = DbField(db_type=DbType.TEXT, default_factory=datetime.now)
```

### 2.2 Create Table Using Migration Commands

```bash
# This is a set of operations under the command line prompt.
pylite-migr init --db mydb.db
pylite-migr create user
pylite-migr upgrade
```

### 2.3 Connect to Database

```python
from pylite_orm import DbConn, DbSession

db = DbConn("mydb.db")
dbs = DbSession(db)
```

### 2.4 Insert Data

```python
user = User(name="Tom", age=25)
dbs.insert(User).item(user).exec()
```

### 2.5 Query Data

```python
users = dbs.select(User).filter(User.age > 20).all()
```

### 2.6 Update Data

```python
user.age = 35
data = user.asdict(exec_unset=True)
dbs.update(User).item(data).filter(User.id == user.id).exec()
```

### 2.7 Delete Data

```python
dbs.delete(User).filter(User.id == user.id).exec()
```

It's that simple!

For project development-level, more complex queries and operations, please read the operation guide.