"""
page_rooms.py —— 房间大厅（我的房间 / 创建房间 / 加入房间）

这是"私密房间制"的入口：用户只能看到自己加入过的房间，
所有回忆都是房间内部的，跨房间互不可见。
"""

import streamlit as st

from core import services


def render() -> None:
    """渲染房间大厅。渲染完成后，调用方负责跳转到具体房间。"""
    user_id = st.session_state["user_id"]

    st.markdown("### 🏠 我的回忆房间")
    st.caption("每个房间都是一间只属于你们的私密小屋，只有房内成员能看到里面的内容。")

    rooms = services.list_user_rooms(user_id)

    col_list, col_action = st.columns([1.5, 1], gap="large")

    # -------------------------------------------------------------------
    # 左栏：房间列表
    # -------------------------------------------------------------------
    with col_list:
        if not rooms:
            st.info("你还没有加入任何房间。先在右边创建一个，或者用邀请码加入同担的群。")
        else:
            for room in rooms:
                # 用 HTML 卡片展示，比默认控件更好看
                role_tag = (
                    '<span class="xh-chip">房主</span>'
                    if room["owner_id"] == user_id
                    else '<span class="xh-chip pink">成员</span>'
                )
                st.markdown(
                    f"""
                    <div class="xh-room">
                        <div class="t">{_esc(room["room_name"])}</div>
                        <div class="s">
                            {role_tag}
                            <span class="xh-chip">邀请码 {_esc(room["room_code"])}</span>
                            <span class="xh-chip">{room["member_count"]} 位成员</span>
                            <span class="xh-chip">{room["memory_count"]} 段回忆</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                # 用 room_code 作为 key，保证每个房间的按钮互相独立
                if st.button(
                    "进入房间 →",
                    key=f"enter_{room['id']}",
                    use_container_width=True,
                ):
                    st.session_state["current_room_id"] = room["id"]
                    st.session_state["current_room_name"] = room["room_name"]
                    st.rerun()

    # -------------------------------------------------------------------
    # 右栏：创建 / 加入
    # -------------------------------------------------------------------
    with col_action:
        tab_create, tab_join = st.tabs(["➕ 创建房间", "🔗 加入房间"])

        # ---------------- 创建 ----------------
        with tab_create:
            with st.form("create_room_form"):
                room_name = st.text_input(
                    "房间名称", placeholder="例如：王力宏演唱会回忆馆"
                )
                room_desc = st.text_input(
                    "一句话简介（可选）", placeholder="2026 年那个夏天"
                )
                room_code = st.text_input(
                    "自定义邀请码（可选）",
                    placeholder="留空自动生成，例如 WLG2026",
                    help="同担输入这个邀请码就能加入房间",
                )
                join_pwd = st.text_input(
                    "加入密码（可选，更私密）",
                    type="password",
                    help="留空则只要知道邀请码就能进；填了就要额外输密码",
                )
                if st.form_submit_button("创建", type="primary", use_container_width=True):
                    result = services.create_room(
                        owner_id=user_id,
                        room_name=room_name,
                        room_code=room_code,
                        description=room_desc,
                        join_password=join_pwd,
                    )
                    if result.ok:
                        st.success(result.message)
                        st.rerun()
                    else:
                        st.error(result.message)

        # ---------------- 加入 ----------------
        with tab_join:
            with st.form("join_room_form"):
                code_input = st.text_input(
                    "房间邀请码", placeholder="例如 WLG2026（不区分大小写）"
                )
                pwd_input = st.text_input(
                    "加入密码（如房间设置了才需要）", type="password"
                )
                if st.form_submit_button("加入", type="primary", use_container_width=True):
                    result = services.join_room(user_id, code_input, pwd_input)
                    if result.ok:
                        st.success(result.message)
                        st.rerun()
                    else:
                        st.error(result.message)


def _esc(text) -> str:
    """把用户输入转义后再拼进 HTML，防止 XSS（比如昵称里写 <script>）。

    Streamlit 渲染 HTML 时不会自动转义，所以必须自己做。
    """
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
