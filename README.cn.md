# pylite-orm

🌍 **语言**: [English](README.md) | **中文**

---

pylite-orm 是一个较新的基于 Python 的 sqlite ORM 轻量工具。为开发者提供简洁、直观的 Sqlite 操作接口。

在已经有很多优秀 Python ORM （如 SQLAlchemy、Tortoise-ORM、Peewee）情况下，为什么还要有pylite-orm？

因为在许多场景中——桌面软件、移动应用、小型CMS、嵌入式系统、自动化脚本，使用sqlite这种单文件数据库时，如果使用前面提到的那些 ORM 会显得很重。 pylite-orm 则提供简单的 API 和极小的内存占用——它只有少量语法，并且整个库仅40Kb大小！这显然就是pylite-orm 存在的价值和优势。

pylite-orm 的特点：

- 简单易用，快速上手
- 代码量少，内存占用小
- 支持事务
- 支持多数据库连接
- 支持多表查询和关联关系（一对一、一对多）
- 支持原生 SQL 查询
- 支持查询结果填充到 Python 对象、列表、字典，以及最流行的Pydantic模型等
- 自带数据迁移工具，生产级可用

如果你熟悉SQLAlchemy/SQLModel、Peewee或其它流行的Python ORM，你立即就能使用pylite-orm，零学习成本。

如果你首次接触 ORM，pylite-orm 能让你快速交付代码，并且，将来掌握其它 ORM 会更加轻松。

### 安装 pylite-orm

```bash
pip install pylite-orm
```

### 入门示例

#### 定义数据模型

```python
from pylite_orm import  DbModel, DbField, DbType
from datetime import datetime

class User(DbModel):
    id = DbField(db_type=DbType.INT, pk=True)
    name = DbField(db_type=DbType.TEXT)
    age = DbField(db_type=DbType.INT)
    created_at = DbField(db_type=DbType.TEXT, default_factory=datetime.now)
```

#### 使用迁移命令创建表

```bash
# 这是一组在命令行中执行的操作
pylite-migr init --db mydb.db
pylite-migr create user
pylite-migr upgrade
```

#### 连接数据库

```python
from pylite_orm import DbConn, DbSession

db = DbConn("mydb.db")
dbs = DbSession(db)
```

#### 插入数据

```python
user = User(name="Tom", age=25)
dbs.insert(User).item(user).exec()
```

#### 查询数据

```python
# 单条查询
user: User = dbs.select(User).filter(User.id == 1).first()
# 多条查询
users: list[User] = dbs.select(User).filter(User.age > 20).all()
# 多条查询（填充到字典）
users_dicts: list[dict] = dbs.select(User).filter(User.age > 20).serial()
```

#### 更新数据

```python
user.age = 35
data = user.asdict(exec_unset=True) # 只更新修改过的字段，即age
dbs.update(User).item(data).filter(User.id == user.id).exec()
```

#### 删除数据

```python
dbs.delete(User).filter(User.id == user.id).exec()
```

一切就是这么简单！

项目开发级、更复杂的查询和操作，请阅读操作指南。