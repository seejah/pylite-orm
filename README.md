# pylite-orm

🌍 **Languages**: **English** | [中文](README.cn.md)

---

`pylite-orm` is a lightweight and relatively new SQLite ORM library for Python. It provides developers with concise and intuitive interfaces for SQLite operations.

Given that there are already many excellent Python ORMs (such as SQLAlchemy, Tortoise-ORM, Peewee), why do we still need pylite-orm ?

Because in many scenarios — desktop software, mobile applications, small CMSs, embedded systems, automation scripts — using a single-file database like SQLite with those ORMs can feel too heavy. pylite-orm offers a simple API and minimal memory footprint — it has only a small amount of syntax, and the entire library is just 40KB in size. These are the core reasons and key advantages behind the existence of pylite-orm.

Features of pylite-orm:

- Simple and easy to use, quick to get started
- Small codebase, low memory usage
- Support for transactions
- Support for multiple database connections
- Support for multi-table queries and relationships (one-to-one, one-to-many)
- Support for native SQL queries
- Support for populating query results into Python objects, lists, dictionaries, and the most popular Pydantic models, etc.
- Built-in data migration tool, production-ready

If you are familiar with SQLAlchemy/SQLModel, Peewee, or other popular Python ORMs, you can start using pylite-orm immediately with zero learning cost.

If you are new to ORMs, pylite-orm allows you to deliver code quickly, and in the future, mastering other ORMs will become even easier.

### Install pylite-orm

```bash
pip install pylite-orm
```

### Getting Started Examples

#### Define Data Model

```python
from pylite_orm import  DbModel, DbField, DbType
from datetime import datetime

class User(DbModel):
    id = DbField(db_type=DbType.INT, pk=True)
    name = DbField(db_type=DbType.TEXT)
    age = DbField(db_type=DbType.INT)
    created_at = DbField(db_type=DbType.TEXT, default_factory=datetime.now)
```

#### Create Table Using Migration Commands

```bash
# This is a set of operations under the command line prompt.
pylite-migr init --db mydb.db
pylite-migr create user
pylite-migr upgrade
```

#### Connect to Database

```python
from pylite_orm import DbConn, DbSession

db = DbConn("mydb.db")
dbs = DbSession(db)
```

#### Insert Data

```python
user = User(name="Tom", age=25)
dbs.insert(User).item(user).exec()
```

#### Query Data

```python
# single query
user: User = dbs.select(User).filter(User.id == 1).first()
# multiple query
users: list[User] = dbs.select(User).filter(User.age > 20).all()
# multiple query (populate to dictionary)
users_dicts: list[dict] = dbs.select(User).filter(User.age > 20).serial()
```

#### Update Data

```python
user.age = 35
data = user.asdict(exec_unset=True) # only update the modified data
dbs.update(User).item(data).filter(User.id == user.id).exec()
```

#### Delete Data

```python
dbs.delete(User).filter(User.id == user.id).exec()
```

It's that simple!

For project development-level, more complex queries and operations, please read the [documentation](https://pylite-orm.n166.net).