"""
app.py —— 星海日记 · 应用入口

运行方式（在项目根目录执行）：
    streamlit run app.py

【整个应用的页面流转逻辑】

        未登录
          │
    ┌─────▼─────┐
    │ 登录/注册  │  ui/page_auth.py
    └─────┬─────┘
          │ 登录成功（写入 st.session_state["user_id"]）
    ┌─────▼─────┐
    │  房间大厅  │  ui/page_rooms.py   ← 创建房间 / 加入房间
    └─────┬─────┘
          │ 点「进入房间」（写入 current_room_id）
    ┌─────▼─────┐
    │  房间内部  │  ui/page_memory.py  ← 发回忆 / 看时间线
    └───────────┘

这个"路由"没有用任何框架，就是根据 session_state 里的两个字段决定渲染哪个页面。
"""

import streamlit as st

from core.config import APP_NAME, APP_SLOGAN, UPLOAD_DIR
from core.db import get_backend_name, init_db
from ui import page_auth, page_memory, page_rooms, styles

# ---------------------------------------------------------------------------
# 1. 页面基础设置（必须是第一个 Streamlit 调用）
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=f"{APP_NAME} · 赛博回忆档案馆",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# 2. 应用启动时初始化数据库
# ---------------------------------------------------------------------------
# @st.cache_resource 保证"建表"这个动作整个进程只执行一次，
# 否则每次页面刷新都会重复连一次数据库。
@st.cache_resource
def _bootstrap() -> str:
    init_db()                 # 建表（已存在的表会自动跳过）
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return get_backend_name()


backend = _bootstrap()

# ---------------------------------------------------------------------------
# 3. 注入全局样式
# ---------------------------------------------------------------------------
styles.inject()


# ---------------------------------------------------------------------------
# 4. 侧边栏：用户信息 + 退出登录
# ---------------------------------------------------------------------------
def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown(f"### 🌌 {APP_NAME}")
        st.caption(APP_SLOGAN)
        st.divider()

        if st.session_state.get("user_id"):
            st.markdown(f"**{st.session_state['nickname']}**")
            st.caption(f"@{st.session_state['username']}")

            # 有进入房间时，给一个"返回大厅"的快捷入口
            if st.session_state.get("current_room_id"):
                if st.button("← 返回房间大厅", use_container_width=True):
                    st.session_state.pop("current_room_id", None)
                    st.session_state.pop("current_room_name", None)
                    st.rerun()

            st.divider()
            if st.button("退出登录", use_container_width=True):
                # 清空整个会话，回到登录页
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        else:
            st.info("请先登录")

        st.divider()
        # 把当前用的数据库类型显示出来，方便你确认到底连的是 SQLite 还是 MySQL
        st.caption(f"数据存储：{backend}")
        st.caption("v0.1.0 · 本地 MVP")


_render_sidebar()


# ---------------------------------------------------------------------------
# 5. 页面路由
# ---------------------------------------------------------------------------
if not st.session_state.get("user_id"):
    # ---- 未登录 → 登录/注册页 ----
    page_auth.render()
elif st.session_state.get("current_room_id"):
    # ---- 已进入某个房间 → 房间内部页 ----
    page_memory.render(
        room_id=st.session_state["current_room_id"],
        room_name=st.session_state.get("current_room_name", ""),
    )
else:
    # ---- 已登录但没选房间 → 房间大厅 ----
    page_rooms.render()
