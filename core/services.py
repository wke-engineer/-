"""
services.py —— 业务逻辑层（房间 / 回忆 / 照片）

【为什么要单独一层？】
界面代码（Streamlit）只负责"画"和"收"，不应该关心 SQL 怎么写。
所有"查数据库、存文件、算权限"的活儿都放在这里。
好处：将来把 Streamlit 换成小程序 + FastAPI，这一层可以原封不动地复用。

    ui/  (界面)  -->  services.py (业务)  -->  db.py + models.py (数据)
"""

import re
import secrets
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select

from core.auth import hash_password, verify_password
from core.config import (
    ALLOWED_IMAGE_EXT,
    CAPTION_MAX_LEN,
    MAX_PHOTOS_PER_MEMORY,
    UPLOAD_DIR,
)
from core.db import get_session
from core.models import Memory, Photo, Room, RoomMember, User


@dataclass
class Result:
    """统一的操作结果：ok 表示成败，message 是提示文案，data 可携带额外数据"""
    ok: bool
    message: str
    data: object | None = None


# ===========================================================================
# 一、房间相关
# ===========================================================================
def _normalize_code(code: str) -> str:
    """规范化邀请码：去空格 + 转大写。
    这样用户输入 'wlg2026' 和 ' WLG2026 ' 都能进同一个房间，避免因大小写进不去。
    """
    return re.sub(r"\s+", "", (code or "")).upper()


def create_room(
    owner_id: int,
    room_name: str,
    room_code: str | None = None,
    description: str = "",
    join_password: str = "",
) -> Result:
    """创建一个私密房间，创建者自动成为房主（owner），并加入房间。"""
    room_name = (room_name or "").strip()
    if not room_name:
        return Result(False, "请填写房间名称")
    if len(room_name) > 100:
        return Result(False, "房间名称太长（最多 100 字）")

    # 没填邀请码就自动生成一个 8 位的，字符集去掉了容易混淆的 0/O/1/I
    if not room_code:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        room_code = "".join(secrets.choice(alphabet) for _ in range(8))
    room_code = _normalize_code(room_code)

    if len(room_code) < 4:
        return Result(False, "邀请码至少 4 位")

    with get_session() as db:
        # 邀请码必须唯一，否则用户输入相同号码会不知道该进哪个房间
        if db.scalar(select(Room).where(Room.room_code == room_code)):
            return Result(False, f"邀请码 {room_code} 已被占用，请换一个")

        room = Room(
            room_code=room_code,
            room_name=room_name,
            description=(description or "").strip()[:255] or None,
            # 加入密码是可选项，填了才存哈希
            join_password_hash=hash_password(join_password) if join_password else None,
            owner_id=owner_id,
        )
        db.add(room)
        db.flush()   # 拿到 room.id

        # 房主也写进成员表，这样"我的房间列表"逻辑就不用特殊处理房主了
        db.add(RoomMember(room_id=room.id, user_id=owner_id, role="owner"))

        db.refresh(room)
        return Result(True, f"房间「{room_name}」创建成功", room)


def join_room(user_id: int, room_code: str, join_password: str = "") -> Result:
    """通过邀请码加入房间"""
    code = _normalize_code(room_code)
    if not code:
        return Result(False, "请输入房间邀请码")

    with get_session() as db:
        room = db.scalar(select(Room).where(Room.room_code == code))
        if room is None:
            return Result(False, "房间不存在，请检查邀请码是否正确")

        # 已经在房间里了，直接放行（幂等，用户重复点不会报错）
        already = db.scalar(
            select(RoomMember).where(
                RoomMember.room_id == room.id, RoomMember.user_id == user_id
            )
        )
        if already:
            return Result(True, f"你已经在「{room.room_name}」里了", room)

        # 校验加入密码
        if room.join_password_hash:
            if not join_password:
                return Result(False, "该房间需要加入密码")
            if not verify_password(join_password, room.join_password_hash):
                return Result(False, "加入密码不正确")

        db.add(RoomMember(room_id=room.id, user_id=user_id, role="member"))
        return Result(True, f"已加入「{room.room_name}」", room)


def list_user_rooms(user_id: int) -> list[dict]:
    """列出某个用户加入的所有房间。

    返回 dict 而不是 ORM 对象，是为了顺带把"成员数""回忆数"一起算出来，
    免得在界面上一行一行动态查（那会产生 N+1 次查询，房间一多就卡）。

    【这里踩过一个坑，值得记下来】
    最初的写法是：
        .join(RoomMember, RoomMember.room_id == Room.id)
        .where(RoomMember.user_id == user_id)
        .group_by(Room.id)
    然后 count(RoomMember.id) 算成员数 —— 结果永远算出 1 个人。
    原因：where 把 RoomMember 过滤成"只有我自己的那一条"了，
    JOIN 出来的表里每人只剩一行，再怎么 count 都只有 1。

    正确做法：把我自己的身份判断放在 where 里用 EXISTS（不去 JOIN 它），
    成员数/回忆数各用一个「独立的关联子查询」来数。
    这样既只发一条 SQL，两个统计口径也互不干扰。
    """
    with get_session() as db:
        # 子查询①：这个房间一共有多少成员（不带当前用户过滤）
        member_count_sq = (
            select(func.count(RoomMember.id))
            .where(RoomMember.room_id == Room.id)
            .correlate(Room)
            .scalar_subquery()
        )

        # 子查询②：这个房间一共有多少段回忆
        memory_count_sq = (
            select(func.count(Memory.id))
            .where(Memory.room_id == Room.id)
            .correlate(Room)
            .scalar_subquery()
        )

        # 主查询：先圈定"我加入的房间"，再用上面两个子查询补充统计值
        stmt = (
            select(
                Room,
                member_count_sq.label("member_count"),
                memory_count_sq.label("memory_count"),
            )
            .where(
                select(RoomMember.id)
                .where(
                    RoomMember.room_id == Room.id,
                    RoomMember.user_id == user_id,
                )
                .exists()
            )
            .order_by(Room.created_at.desc())
        )

        rows = db.execute(stmt).all()
        return [
            {
                "id": room.id,
                "room_code": room.room_code,
                "room_name": room.room_name,
                "description": room.description,
                "owner_id": room.owner_id,
                "created_at": room.created_at,
                "member_count": member_count,
                "memory_count": memory_count,
            }
            for room, member_count, memory_count in rows
        ]


def get_room_members(room_id: int) -> list[dict]:
    """房间成员列表（谁在这个房间里）"""
    with get_session() as db:
        stmt = (
            select(User, RoomMember.role, RoomMember.joined_at)
            .join(RoomMember, RoomMember.user_id == User.id)
            .where(RoomMember.room_id == room_id)
            .order_by(RoomMember.joined_at.asc())
        )
        return [
            {
                "id": u.id,
                "nickname": u.nickname,
                "username": u.username,
                "role": role,
                "joined_at": joined_at,
            }
            for u, role, joined_at in db.execute(stmt).all()
        ]


def is_member(user_id: int, room_id: int) -> bool:
    """【权限核心】判断用户是否属于这个房间。

    每一次"读写房间内容"之前都必须调用它。
    这是"私密房间"这条产品红线的技术实现 —— 不在房间里，就什么都看不到。
    """
    with get_session() as db:
        return db.scalar(
            select(RoomMember.id).where(
                RoomMember.room_id == room_id, RoomMember.user_id == user_id
            )
        ) is not None


# ===========================================================================
# 二、照片文件存储
# ===========================================================================
def save_uploaded_photo(file_bytes: bytes, original_name: str, memory_id: int) -> str:
    """把上传的照片写到磁盘，返回相对路径（存进数据库的就是这个）。

    【为什么文件名要重命名成随机串？】
    用户上传的文件名千奇百怪，可能有中文、空格、甚至 "../../etc/passwd" 这种
    路径穿越攻击。所以：忽略原文件名，只保留后缀，主体用随机十六进制。
    这样既安全，也天然避免了同名覆盖。
    """
    ext = Path(original_name or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        ext = ".jpg"      # 拿不到合法后缀时兜底

    # 每个回忆一个子目录，避免单个目录下几万个文件（某些文件系统会变慢）
    sub_dir = UPLOAD_DIR / str(memory_id)
    sub_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{secrets.token_hex(16)}{ext}"     # 32 位随机十六进制，基本不可能撞名
    target = sub_dir / filename

    with open(target, "wb") as f:
        f.write(file_bytes)

    # 统一用 / 分隔符存库，跨平台（Windows/Linux）都不会出问题
    return f"{memory_id}/{filename}"


def delete_photo_file(relative_path: str) -> None:
    """删除磁盘上的照片文件（数据库记录删除后调用），失败静默忽略"""
    try:
        (UPLOAD_DIR / relative_path).unlink(missing_ok=True)
    except OSError:
        pass


# ===========================================================================
# 三、回忆（日记）相关
# ===========================================================================
def create_memory(
    room_id: int,
    user_id: int,
    title: str,
    content: str,
    photos: list[dict],
) -> Result:
    """创建一篇回忆。

    photos 是一个列表，每一项形如：
        {"bytes": b"...", "name": "IMG_001.jpg", "caption": "最后一首歌的灯海"}

    【重要：为什么用 with 事务包起来？】
    一次"写回忆"要往数据库插 1 条 memories + N 条 photos。
    必须保证要么全部成功，要么全部失败。否则会出现"日记存了但照片丢了"的脏数据。
    get_session 会在出错时自动 rollback。
    """
    title = (title or "").strip()
    if not title:
        return Result(False, "请填写标题")
    if len(title) > 120:
        return Result(False, "标题太长（最多 120 字）")
    if not content.strip() and not photos:
        return Result(False, "至少写点什么，或者传一张照片")

    # 再校验一次权限 —— 不信任界面传进来的 room_id
    if not is_member(user_id, room_id):
        return Result(False, "你不在这个房间里，无法发布")

    if len(photos) > MAX_PHOTOS_PER_MEMORY:
        return Result(False, f"一次最多上传 {MAX_PHOTOS_PER_MEMORY} 张照片")

    with get_session() as db:
        memory = Memory(
            room_id=room_id,
            user_id=user_id,
            title=title,
            content=content or "",
        )
        db.add(memory)
        db.flush()      # 拿到 memory.id，后面存文件要用它当目录名

        try:
            for index, item in enumerate(photos):
                # 注释超长就截断，保证绝不违反 50 字的产品约束
                caption = (item.get("caption") or "").strip()[:CAPTION_MAX_LEN]
                rel_path = save_uploaded_photo(
                    item["bytes"], item.get("name", ""), memory.id
                )
                db.add(
                    Photo(
                        memory_id=memory.id,
                        file_path=rel_path,
                        original_name=(item.get("name") or "")[:255],
                        caption=caption,
                        sort_order=index,      # 保留用户上传顺序
                    )
                )
        except OSError as exc:
            # 磁盘写失败 —— 抛出去让 get_session 回滚数据库，两边保持一致
            raise RuntimeError(f"照片保存失败：{exc}") from exc

        db.refresh(memory)
        return Result(True, "这段回忆已经封存进档案馆了 ✨", memory)


def list_memories(room_id: int, user_id: int, limit: int = 50) -> list[dict]:
    """读取某个房间的回忆列表（按时间倒序），照片一起带出来。

    【重点：过滤要下推到 SQL，不能全表捞出来再在 Python 里过滤】
    where 条件里必须同时有 room_id 和成员校验，数据库只返回这个房间的数据。
    """
    if not is_member(user_id, room_id):
        return []       # 权限兜底：不是成员就直接返回空

    with get_session() as db:
        stmt = (
            select(Memory, User.nickname)
            .join(User, User.id == Memory.user_id)
            .where(Memory.room_id == room_id)
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )
        rows = db.execute(stmt).all()

        result: list[dict] = []
        for memory, nickname in rows:
            photos = [
                {
                    "id": p.id,
                    "file_path": p.file_path,
                    "caption": p.caption,
                    "original_name": p.original_name,
                    "abs_path": str(UPLOAD_DIR / p.file_path),
                }
                for p in memory.photos        # 已按 sort_order 排好
            ]
            result.append(
                {
                    "id": memory.id,
                    "title": memory.title,
                    "content": memory.content,
                    "created_at": memory.created_at,
                    "author": nickname,
                    "photos": photos,
                }
            )
        return result


def get_room(room_id: int) -> dict | None:
    """按 id 取房间基本信息"""
    with get_session() as db:
        room = db.get(Room, room_id)
        if room is None:
            return None
        return {
            "id": room.id,
            "room_code": room.room_code,
            "room_name": room.room_name,
            "description": room.description,
            "owner_id": room.owner_id,
            "has_password": room.join_password_hash is not None,
            "created_at": room.created_at,
        }


def delete_memory(memory_id: int, user_id: int) -> Result:
    """删除一篇回忆（只有作者本人能删），照片文件和数据库记录一起清掉。

    【顺序很重要】先删数据库、提交成功，再删磁盘文件。
    如果反过来（先删文件再删库），万一数据库删除失败回滚了，
    库里还留着记录，但文件已经没了 —— 页面就会显示一堆裂图。
    这个顺序最坏情况只是"文件成了孤儿"，不会出现"记录指向不存在的文件"。
    """
    with get_session() as db:
        memory = db.get(Memory, memory_id)
        if memory is None:
            return Result(False, "这段回忆不存在")
        if memory.user_id != user_id:
            return Result(False, "只能删除自己写的回忆")

        # 先记住文件路径，等数据库删完再删文件
        paths = [p.file_path for p in memory.photos]

        db.delete(memory)      # cascade 会连带删掉 photos 表的记录
        # 退出 with 时才会 commit。commit 成功 = 数据库这边确定删干净了。

    # 走到这里说明事务已提交，现在才动磁盘文件
    for p in paths:
        delete_photo_file(p)

    return Result(True, "已删除")
