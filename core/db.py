"""
db.py —— 数据库连接与会话管理

【核心概念：Engine（引擎）与 Session（会话）】
    Engine   = 连接池 + 数据库方言。整个应用只需要一个，进程启动时创建一次。
    Session  = 一次"业务操作"的上下文。增删改查都通过它，用完要关。

【为什么用 contextmanager（with 语法）？】
    with get_session() as db:
        db.add(obj)

无论中间成功还是抛异常，退出 with 时都会自动 commit / rollback / close。
这样能杜绝"忘记关闭连接导致连接池耗尽"这类经典事故。
"""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from core.config import DATABASE_URL, IS_SQLITE
from core.models import Base

# ---------------------------------------------------------------------------
# 1. 创建引擎
# ---------------------------------------------------------------------------
# pool_pre_ping=True：每次从连接池取连接前先 ping 一下。
# 因为 MySQL 默认 8 小时空闲就断开连接，不 ping 的话会报 "MySQL server has gone away"。
_engine_kwargs: dict = {"pool_pre_ping": True, "future": True, "echo": False}

if IS_SQLITE:
    # SQLite 是单文件数据库，Streamlit 会多线程调用，必须关掉线程检查，
    # 否则会抛 "SQLite objects created in a thread can only be used in that same thread"
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)


# SQLite 默认不开启外键约束，需要手动打开，
# 否则 models.py 里写的 ondelete="CASCADE" 会失效（删回忆时照片变孤儿数据）。
if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ---------------------------------------------------------------------------
# 2. 会话工厂
# ---------------------------------------------------------------------------
# expire_on_commit=False：commit 之后对象数据依然可读。
# 默认 True 的话，commit 后访问 obj.id 会触发一次额外查询，容易踩坑。
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_session() -> Iterator[Session]:
    """获取一个数据库会话（推荐用法）。

    用法：
        with get_session() as db:
            db.add(user)          # 不需要手动 commit，退出 with 时自动提交
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()        # 出任何错就整体回滚，保证数据不会只改一半
        raise
    finally:
        session.close()


def init_db() -> None:
    """建表。

    Base.metadata 里记录了所有继承 Base 的模型，
    create_all 会为"还不存在的表"执行 CREATE TABLE，已存在的表会被跳过（幂等，可重复执行）。
    """
    Base.metadata.create_all(bind=engine)


def get_backend_name() -> str:
    """返回当前使用的数据库类型，界面上展示用"""
    return "SQLite" if IS_SQLITE else "MySQL"
