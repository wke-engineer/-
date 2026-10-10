"""
models.py —— 数据库表结构定义（ORM 模型）

【什么是 ORM？】
ORM = Object Relational Mapping（对象关系映射）。
有了它，你就不用手写 "CREATE TABLE ..." 和 "SELECT * FROM ..."，
而是用 Python 类来代表表、用 Python 对象来代表一行数据。

    一个类    <==>  一张表
    一个属性  <==>  一个字段
    一个实例  <==>  一行记录

【本项目的 5 张核心表】
    users        用户
    rooms        私密房间
    room_members 房间成员（用户 ↔ 房间 的多对多关系表）
    memories     一篇回忆（= 一组照片 + 一段长日记）
    photos       单张照片（挂在某篇回忆下面，带 ≤50 字注释）

【表之间的关系图】

    users ──< room_members >── rooms
      │                          │
      │                          │
      └──────< memories >────────┘
                  │
                  │
               < photos >

    "──<" 表示"一对多"：一个用户可以有很多条 memories，反过来一条 memory 只属于一个用户。
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。

    SQLAlchemy 会收集所有继承自 Base 的子类，知道一共要建哪些表。
    相当于给所有表发了一张"户口本"。
    """


# ===========================================================================
# 表 1：users —— 用户表
# ===========================================================================
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 登录名。unique=True 让数据库层面保证"不会有两个人同名"，
    # 这是最后一道防线 —— 即使代码写错了，数据库也会拒绝重复插入。
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # 昵称：展示给其他粉丝看的名字，可以和登录名不同
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)

    # 【安全】绝不存明文密码！
    # 这里存的是 "算法$盐$哈希值" 这样的一串，由 auth.py 里的哈希函数生成。
    # 哈希是不可逆的，就算数据库泄露，攻击者也还原不出原始密码。
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # 关系属性（不产生数据库字段，只是方便 Python 里 user.memories 直接取到列表）
    #
    # 【passive_deletes=True 是什么意思？】
    # 默认情况下，SQLAlchemy 删除一个 User 时，会先把它的子记录（memories、memberships）
    # 的 user_id 全部改成 NULL，再删自己。但这两个字段是 NOT NULL，会直接报完整性错误。
    # 加上 passive_deletes=True 后，SQLAlchemy 就不管了，交给数据库的
    # ON DELETE CASCADE 去删 —— 这才是外键该干的活，而且只需一条 SQL，更快。
    memories: Mapped[list["Memory"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    memberships: Mapped[list["RoomMember"]] = relationship(
        back_populates="user", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


# ===========================================================================
# 表 2：rooms —— 私密房间表
# ===========================================================================
class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 房间邀请码（对应需求里的"专属群号"，比如 WLG2026）。
    # unique=True 保证一个邀请码只能对应一个房间。
    room_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    room_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 房间简介，可为空
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 【安全升级】光靠邀请码，知道号码的人就能进。
    # 所以再挂一道可选的加入密码（哈希存储）。MVP 阶段可以不填。
    join_password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 房主（创建者）。ondelete="SET NULL" 表示房主注销后房间保留，只是没有房主了。
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # 删除房间时，房间下的 memories / room_members 由数据库 ON DELETE CASCADE 清理
    memories: Mapped[list["Memory"]] = relationship(
        back_populates="room", passive_deletes=True
    )
    members: Mapped[list["RoomMember"]] = relationship(
        back_populates="room", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Room id={self.id} code={self.room_code!r} name={self.room_name!r}>"


# ===========================================================================
# 表 3：room_members —— 房间成员表（多对多关系的"中间表"）
# ===========================================================================
class RoomMember(Base):
    __tablename__ = "room_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 外键：指向 rooms.id。数据库会强制保证"不能把成员挂到一个不存在的房间上"
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 角色：owner（房主）/ member（普通成员），为以后的权限控制留口子
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")

    joined_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    room: Mapped["Room"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")

    # 【非常关键】联合唯一约束：同一个人不能重复加入同一个房间。
    # 没有它，用户连点两次"加入"就会产生两条重复记录，成员数会变成 2。
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_room_user"),
    )

    def __repr__(self) -> str:
        return f"<RoomMember room={self.room_id} user={self.user_id} role={self.role}>"


# ===========================================================================
# 表 4：memories —— 回忆表（一篇日记 / 一次回忆）
# ===========================================================================
class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 一条回忆必须属于某个房间（私密性靠这个字段保证）
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 也必须知道是谁写的
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False)

    # Text 类型不限制长度，用来放"长日记"
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    room: Mapped["Room"] = relationship(back_populates="memories")
    user: Mapped["User"] = relationship(back_populates="memories")

    # 照片按 sort_order 排序，保证每次打开顺序一致（用户上传的顺序）
    photos: Mapped[list["Photo"]] = relationship(
        back_populates="memory",
        cascade="all, delete-orphan",   # 删回忆时，它下面的照片记录一并删除
        order_by="Photo.sort_order",
    )

    # 复合索引：查询"某房间的回忆列表，按时间倒序"是最高频的操作，加索引会快很多
    __table_args__ = (
        Index("ix_memories_room_created", "room_id", "created_at"),
    )

    @property
    def photo_count(self) -> int:
        """照片张数（模板里直接显示用）"""
        return len(self.photos)

    def __repr__(self) -> str:
        return f"<Memory id={self.id} title={self.title!r}>"


# ===========================================================================
# 表 5：photos —— 照片表
# ===========================================================================
class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 归属的回忆。ondelete="CASCADE"：回忆被删，照片记录自动跟着删
    memory_id: Mapped[int] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 【只存路径，不存图片本身】相对 uploads/ 的路径，例如 "3/a1b2c3d4.jpg"
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)

    # 用户上传时的原始文件名，纯展示用（免得界面上全是一串随机字符）
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 这张照片下面那句 ≤50 字的注释
    caption: Mapped[str] = mapped_column(String(50), nullable=False, default="")

    # 排序序号，保持用户上传时的先后顺序
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    memory: Mapped["Memory"] = relationship(back_populates="photos")

    def __repr__(self) -> str:
        return f"<Photo id={self.id} memory={self.memory_id}>"
