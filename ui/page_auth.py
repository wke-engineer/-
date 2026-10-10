"""
page_auth.py —— 登录 / 注册页面

Streamlit 的会话机制说明（很重要）：
    st.session_state 是一个"每个浏览器标签页各自独立"的字典。
    页面每次交互（点按钮、输文字）整个脚本会从头再跑一遍，
    但 session_state 里的数据会保留下来。
    所以"当前登录的是谁"就存在 st.session_state["user_id"] 里。
"""

import streamlit as st

from core import auth
from ui import styles


def render() -> None:
    """渲染登录/注册界面。用户未登录时调用。"""
    styles.hero("星海日记", "把散场的夜晚，装进一间不会关灯的房间")

    # 左右留白，表单居中
    left, mid, right = st.columns([1, 1.6, 1])
    with mid:
        tab_login, tab_register = st.tabs(["🔑 登录", "✨ 注册新账号"])

        # ---------------- 登录 ----------------
        with tab_login:
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("用户名", placeholder="例如 xiaowang")
                password = st.text_input("密码", type="password", placeholder="至少 6 位")
                submitted = st.form_submit_button("进入档案馆", type="primary", use_container_width=True)

            if submitted:
                result = auth.login(username, password)
                if result.ok:
                    # 登录成功：把用户信息写进会话状态，页面下一轮就变成"已登录"
                    _set_logged_in(result.user)
                    st.success(result.message)
                    st.rerun()
                else:
                    st.error(result.message)

        # ---------------- 注册 ----------------
        with tab_register:
            with st.form("register_form", clear_on_submit=False):
                new_username = st.text_input(
                    "用户名", placeholder="3-20 位字母/数字/下划线",
                    help="用于登录，注册后不可修改",
                )
                new_nickname = st.text_input(
                    "昵称", placeholder="展示给同担看，比如「小八」"
                )
                new_password = st.text_input(
                    "密码", type="password", placeholder="至少 6 位"
                )
                confirm_password = st.text_input(
                    "确认密码", type="password", placeholder="再输一遍"
                )
                reg_submitted = st.form_submit_button(
                    "创建账号", type="primary", use_container_width=True
                )

            if reg_submitted:
                # 前端先做一次一致性校验，省一次无意义的数据库往返
                if new_password != confirm_password:
                    st.error("两次输入的密码不一致")
                else:
                    result = auth.register(new_username, new_nickname, new_password)
                    if result.ok:
                        _set_logged_in(result.user)
                        st.success("注册成功，欢迎来到星海日记 ✨")
                        st.rerun()
                    else:
                        st.error(result.message)

        st.caption("提示：注册即表示你承诺只上传自己拥有版权的照片与文字。")


def _set_logged_in(user) -> None:
    """把登录状态写进会话。

    只存 id / username / nickname 这几个必要字段，
    不要把整个 ORM 对象塞进 session_state —— ORM 对象绑定了数据库会话，
    跨多次页面刷新后会因为会话已关闭而报 DetachedInstanceError。
    """
    st.session_state["user_id"] = user.id
    st.session_state["username"] = user.username
    st.session_state["nickname"] = user.nickname
