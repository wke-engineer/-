"""
scripts/init_db.py —— 数据库初始化脚本（命令行）

用法（项目根目录执行）：
    python scripts/init_db.py            # 只建表
    python scripts/init_db.py --demo     # 建表 + 灌一份演示数据

【为什么需要这个脚本？】
app.py 启动时也会自动建表，但如果想在不打开网页的情况下：
  - 确认数据库连接是否正常
  - 提前把表建好
  - 灌一批数据方便演示
就跑这个脚本。
"""

import sys
from pathlib import Path

# 把项目根目录加到模块搜索路径里，
# 否则直接运行 scripts/init_db.py 时会 import 不到 core 包
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, select  # noqa: E402

from core import auth, services  # noqa: E402
from core.config import APP_NAME, UPLOAD_DIR  # noqa: E402
from core.db import engine, get_backend_name, init_db  # noqa: E402


def build_tables() -> None:
    """建表"""
    print(f"[1/3] 目标数据库：{get_backend_name()}")
    print(f"      连接串：{engine.url.render_as_string(hide_password=True)}")
    init_db()

    # 建完之后把实际生成的表名打出来，方便肉眼核对
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    print(f"[2/3] 表已就绪（{len(tables)} 张）：{', '.join(tables)}")


def seed_demo() -> None:
    """灌演示数据：1 个用户 + 1 个房间 + 1 篇回忆

    这是幂等的 —— 如果演示账号已存在，就跳过，重复跑不会产生重复数据。
    """
    from core.db import get_session
    from core.models import Room, User

    demo_username = "demo"
    demo_password = "demo123"

    with get_session() as db:
        existing = db.scalar(select(User).where(User.username == demo_username))
        if existing:
            print("      演示账号已存在，跳过灌数据")
            return

    # 复用业务层函数，保证演示数据和真实用户走的是同一套逻辑
    r = auth.register(demo_username, "演示小助手", demo_password)
    if not r.ok:
        print(f"      演示账号创建失败：{r.message}")
        return
    demo_user_id = r.user.id

    room_r = services.create_room(
        owner_id=demo_user_id,
        room_name="王力宏演唱会回忆馆",
        room_code="WLG2026",
        description="2026 年那个夏天，我们都没走。",
    )
    if not room_r.ok:
        print(f"      演示房间创建失败：{room_r.message}")
        return
    room_id = room_r.data.id

    # 一篇不带照片的纯文字回忆（照片需要真实文件，脚本里就不造了）
    mem_r = services.create_memory(
        room_id=room_id,
        user_id=demo_user_id,
        title="散场后我们谁都没走",
        content=(
            "最后一首歌的前奏响起的时候，全场突然安静了一秒。\n"
            "然后是几万人一起唱的声音。\n\n"
            "灯海被举起来的那一刻，我忽然意识到，\n"
            "这不是结束，这是我们共同拥有的一个坐标。\n\n"
            "散场以后，我们谁都没走。"
        ),
        photos=[],
    )
    if not mem_r.ok:
        print(f"      演示回忆创建失败：{mem_r.message}")
        return

    print("      演示数据已写入：")
    print(f"        账号：{demo_username} / {demo_password}")
    print(f"        房间邀请码：WLG2026")


def main() -> None:
    print(f"=== {APP_NAME} · 数据库初始化 ===")
    build_tables()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[3/3] 照片目录已就绪：{UPLOAD_DIR}")

    if "--demo" in sys.argv:
        print("--- 灌演示数据 ---")
        seed_demo()

    print("\n✅ 初始化完成。接下来运行： streamlit run app.py")


if __name__ == "__main__":
    main()
