"""
scripts/smoke_test.py —— 端到端冒烟测试

作用：不打开网页，直接用代码把整条主链路跑一遍，验证后端逻辑是否正确。
      （不需要 pytest，直接 python scripts/smoke_test.py 就能跑）

覆盖的链路：
    注册 → 登录 → 创建房间 → 另一个用户加入房间 → 发一篇带照片的回忆
    → 读取时间线 → 权限隔离验证 → 清理测试数据

【为什么要做冒烟测试？】
界面上的操作点几下很快，但要验证"权限没漏、数据没错、事务没脏"，
写脚本跑一遍是最靠得住的方式。每次改完代码跑一次，30 秒内知道有没有搞坏东西。
"""

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from core import auth, services  # noqa: E402
from core.db import get_session, init_db  # noqa: E402
from core.models import Memory, Photo, Room, RoomMember, User  # noqa: E402

PASS, FAIL = "✅", "❌"
_failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    """断言小工具：条件成立打 ✅，不成立打 ❌ 并记下来"""
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}  {detail}")
        _failures.append(label)


def make_fake_png() -> bytes:
    """造一张 1x1 像素的合法 PNG（用来测上传，不依赖任何外部图片文件）"""
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def main() -> int:
    print("=== 星海日记 · 冒烟测试 ===\n")
    init_db()

    suffix = random.randint(10000, 99999)
    ua_name, ub_name = f"tester_a_{suffix}", f"tester_b_{suffix}"

    # ---------------- 1. 认证 ----------------
    print("[1] 用户认证")
    ra = auth.register(ua_name, "测试甲", "pwd123456")
    check("注册用户 A", ra.ok, ra.message)
    rb = auth.register(ub_name, "测试乙", "pwd123456")
    check("注册用户 B", rb.ok, rb.message)

    a_id, b_id = ra.user.id, rb.user.id

    check("重复用户名被拒绝", not auth.register(ua_name, "重名", "pwd123456").ok)
    check("弱密码被拒绝", not auth.register(f"weak_{suffix}", "弱", "123").ok)
    check("正确密码可登录", auth.login(ua_name, "pwd123456").ok)
    check("错误密码被拒绝", not auth.login(ua_name, "wrong_pwd").ok)
    check("不存在的用户被拒绝", not auth.login(f"nobody_{suffix}", "pwd123456").ok)

    # 密码哈希验证：数据库里绝不能是明文
    with get_session() as db:
        stored = db.scalar(select(User.password_hash).where(User.id == a_id))
    check("密码以哈希形式存储", stored != "pwd123456" and stored.startswith("pbkdf2_sha256$"),
          f"实际值={stored[:30]}...")

    # ---------------- 2. 房间 ----------------
    print("\n[2] 私密房间")
    room_code = f"TEST{suffix}"
    rc = services.create_room(a_id, "测试回忆馆", room_code, "冒烟测试用")
    check("创建房间", rc.ok, rc.message)
    room_id = rc.data.id

    check("重复邀请码被拒绝", not services.create_room(a_id, "撞码房间", room_code).ok)
    check("创建者是房间成员", services.is_member(a_id, room_id))
    check("非成员默认无权限", not services.is_member(b_id, room_id))

    # B 加入
    rj = services.join_room(b_id, room_code.lower())   # 故意用小写，验证大小写不敏感
    check("邀请码大小写不敏感，B 成功加入", rj.ok, rj.message)
    check("重复加入是幂等的", services.join_room(b_id, room_code).ok)
    check("B 加入后成为成员", services.is_member(b_id, room_id))

    members = services.get_room_members(room_id)
    check("成员数为 2", len(members) == 2, f"实际={len(members)}")
    roles = {m["id"]: m["role"] for m in members}
    check("A 是房主、B 是成员", roles.get(a_id) == "owner" and roles.get(b_id) == "member")

    # 带密码的房间
    rp = services.create_room(a_id, "带锁房间", f"LOCK{suffix}", join_password="secret666")
    check("创建带密码的房间", rp.ok, rp.message)
    check("密码错误无法加入", not services.join_room(b_id, f"LOCK{suffix}", "wrong").ok)
    check("不输密码无法加入", not services.join_room(b_id, f"LOCK{suffix}", "").ok)
    check("密码正确可加入", services.join_room(b_id, f"LOCK{suffix}", "secret666").ok)
    check("不存在的房间被拒绝", not services.join_room(b_id, f"NOSUCH{suffix}").ok)

    # ---------------- 3. 回忆 + 照片 ----------------
    print("\n[3] 回忆与照片")
    photos = [
        {"bytes": make_fake_png(), "name": "IMG_001.png", "caption": "最后一首歌的灯海"},
        {"bytes": make_fake_png(), "name": "IMG_002.png", "caption": ""},
        # 故意传一条超过 50 字的注释，验证后端会截断
        {"bytes": make_fake_png(), "name": "IMG_003.png", "caption": "字" * 80},
    ]
    rm = services.create_memory(room_id, a_id, "散场后谁都没走", "那天晚上我们唱到了最后。", photos)
    check("创建带 3 张照片的回忆", rm.ok, rm.message)
    memory_id = rm.data.id

    check("空内容被拒绝", not services.create_memory(room_id, a_id, "空", "  ", []).ok)
    check("无标题被拒绝", not services.create_memory(room_id, a_id, "", "正文", []).ok)

    # 越权测试：不在房间里的人不能发帖
    outsider = auth.register(f"outsider_{suffix}", "路人", "pwd123456").user.id
    check("非成员不能发回忆", not services.create_memory(room_id, outsider, "越权", "内容", []).ok)

    # 照片落盘与注释长度
    with get_session() as db:
        saved = db.scalars(
            select(Photo).where(Photo.memory_id == memory_id).order_by(Photo.sort_order)
        ).all()
    check("照片记录数为 3", len(saved) == 3, f"实际={len(saved)}")
    check("照片按上传顺序排序", [p.sort_order for p in saved] == [0, 1, 2])
    check("注释被截断到 50 字", len(saved[2].caption) == 50, f"实际={len(saved[2].caption)}")

    from core.config import UPLOAD_DIR
    all_exist = all((UPLOAD_DIR / p.file_path).exists() for p in saved)
    check("照片文件全部落盘成功", all_exist)
    check("文件名已随机化（不含原始名）", all("IMG_" not in p.file_path for p in saved))

    # ---------------- 4. 读取与权限隔离 ----------------
    print("\n[4] 时间线与权限隔离")
    timeline_owner = services.list_memories(room_id, a_id)
    check("A 能看到 1 段回忆", len(timeline_owner) == 1, f"实际={len(timeline_owner)}")

    mem = timeline_owner[0]
    check("回忆标题正确", mem["title"] == "散场后谁都没走")
    check("作者昵称正确", mem["author"] == "测试甲")
    check("照片随回忆一起返回", len(mem["photos"]) == 3)
    check("照片路径可直接用于展示", Path(mem["photos"][0]["abs_path"]).exists())

    check("非成员读时间线返回空", services.list_memories(room_id, outsider) == [])

    # ---------------- 5. 房间统计 ----------------
    print("\n[5] 房间统计")
    rooms = services.list_user_rooms(a_id)
    target = next((r for r in rooms if r["id"] == room_id), None)
    check("房间出现在 A 的列表里", target is not None)
    if target:
        check("成员数统计正确", target["member_count"] == 2, f"实际={target['member_count']}")
        check("回忆数统计正确", target["memory_count"] == 1, f"实际={target['memory_count']}")

    check("B 也能看到同一房间", any(r["id"] == room_id for r in services.list_user_rooms(b_id)))
    check("路人看不到该房间", not any(r["id"] == room_id for r in services.list_user_rooms(outsider)))

    # ---------------- 6. 删除 ----------------
    print("\n[6] 删除与级联清理")
    check("别人不能删我的回忆", not services.delete_memory(memory_id, b_id).ok)
    paths_before = [p.file_path for p in saved]
    check("作者可以删除", services.delete_memory(memory_id, a_id).ok)

    with get_session() as db:
        check("回忆记录已删除",
              db.scalar(select(Memory.id).where(Memory.id == memory_id)) is None)
        check("照片记录级联删除",
              db.scalar(select(Photo.id).where(Photo.memory_id == memory_id)) is None)
    check("照片文件已从磁盘清除",
          not any((UPLOAD_DIR / p).exists() for p in paths_before))

    # ---------------- 7. 清理测试数据 ----------------
    print("\n[7] 清理测试数据")
    with get_session() as db:
        test_users = db.scalars(
            select(User).where(User.username.like(f"%{suffix}%"))
        ).all()
        test_rooms = db.scalars(
            select(Room).where(Room.room_code.like(f"%{suffix}%"))
        ).all()
        for r in test_rooms:
            db.delete(r)
        for u in test_users:
            db.delete(u)
    check(f"已清理 {len(test_users)} 个测试用户 / {len(test_rooms)} 个测试房间", True)

    # ---------------- 结果 ----------------
    print("\n" + "=" * 46)
    if _failures:
        print(f"{FAIL} 失败 {len(_failures)} 项：")
        for f in _failures:
            print(f"   - {f}")
        print("=" * 46)
        return 1
    print(f"{PASS} 全部通过 —— 主链路：注册/登录/建房/加房/发回忆/传照片/读时间线/权限隔离/级联删除")
    print("=" * 46)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:            # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"\n{FAIL} 测试过程中抛出异常：{exc}")
        sys.exit(1)
