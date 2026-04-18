# pylite-orm

🌍 **语言**: [English](README.md) | **中文**

---

pylite-orm 是一个较新的基于 Python 的 sqlite ORM 轻量工具。为开发者提供简洁、直观的 Sqlite 操作接口。

在已经存在很多优秀的 Python ORM 框架（如 SQLAlchemy、Tortoise-ORM、Peewee）背景下，为什么要使用pylite-orm？

很显然，在一些特定场合，如桌面软件、移动应用、嵌入式系统、脚本开发，通常使用sqlite这种单文件数据库，这时使用前面提到的那些 ORM 显得很重，而 pylite-orm 提供更简单的 API 和更小的内存占用——它只有几个简单语法，并且仅仅40K大小！这就是pylite-orm 存在的意义。

pylite-orm 的特点：

- 简单易用，快速上手
- 代码量少，内存占用小
- 支持事务
- 支持多数据库连接
- 支持多表查询和关联关系（一对一、一对多）
- 支持原生 SQL 查询
- 支持查询结果填充到 Python 对象、列表、字典，以及最流行的Pydantic模型等
- 自带数据迁移工具，生产级可用

如果你熟悉SQLAlchemy、Peewee或其它流行的Python ORM框架，你立即就能使用pylite-orm。

## 1 安装 PyLite-ORM

```bash
pip install pylite-orm
```

## 2 入门示例

### 2.1 定义数据模型

```python
from pylite_orm import  DbModel, DbField, DbType
from datetime import datetime

class User(Model):
    id = DbField(db_type=DbType.INT, pk=True)
    name = DbField(db_type=DbType.TEXT)
    age = DbField(db_type=DbType.INT)
    created_at = DbField(db_type=DbType.TEXT, default_factory=datetime.now)
```

### 2.2 使用迁移命令创建表

```bash
# 这是一组在命令行中执行的操作
pylite-migr init --db mydb.db
pylite-migr create user
pylite-migr upgrade
```

### 2.3 连接数据库

```python
from pylite_orm import DbConn, DbSession

db = DbConn("mydb.db")
dbs = DbSession(db)
```

### 2.4 插入数据

```python
user = User(name="Tom", age=25)
dbs.insert(User).item(user).exec()
```

### 2.5 查询数据

```python
users = dbs.select(User).filter(User.age > 20).all()
```

### 2.6 更新数据

```python
user.age = 35
data = user.asdict(exec_unset=True)
dbs.update(User).item(data).filter(User.id == user.id).exec()
```

### 2.7 删除数据

```python
dbs.delete(User).filter(User.id == user.id).exec()
```

一切就是这么简单！

项目开发级、更复杂的查询和操作，请阅读操作指南。