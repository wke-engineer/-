"""
page_memory.py —— 房间内部页（发布回忆 / 回忆时间线）

这是整个 MVP 的核心页面，包含两个标签页：
    ① 写新回忆：标题 + 长日记 + 批量上传照片 + 每张照片 ≤50 字注释
    ② 回忆时间线：按时间倒序展示房间里所有的回忆

【Streamlit 的一个关键特性，必须理解】
页面上的每一次交互（点按钮、改输入、传文件）都会让 整个脚本从头重新执行一遍。
所以：
  - 上传的文件我们要从 st.file_uploader 的返回值里拿（它会自动保留）
  - 任何"处理结果"的提示，处理完就消失（因为脚本重跑了），这是正常的
"""

import streamlit as st

from core import services
from core.config import CAPTION_MAX_LEN, MAX_PHOTOS_PER_MEMORY, MAX_UPLOAD_MB
from ui.page_rooms import _esc


def render(room_id: int, room_name: str) -> None:
    """渲染房间内部页面"""
    user_id = st.session_state["user_id"]

    # ---------------- 顶部：房间信息条 ----------------
    room = services.get_room(room_id)
    if room is None:
        st.error("房间不存在或已被删除")
        if st.button("← 返回房间大厅"):
            _back_to_lobby()
        return

    # 【权限校验】不是房间成员，直接挡住，什么都不给看
    if not services.is_member(user_id, room_id):
        st.warning("你不是这个房间的成员，无法查看内容。")
        if st.button("← 返回房间大厅"):
            _back_to_lobby()
        return

    members = services.get_room_members(room_id)

    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.markdown(f"## {_esc(room['room_name'])}")
        pwd_tag = '<span class="xh-chip pink">已设密码</span>' if room["has_password"] else ""
        st.markdown(
            f'<span class="xh-chip">邀请码 {_esc(room["room_code"])}</span>'
            f'<span class="xh-chip">{len(members)} 位成员</span>{pwd_tag}',
            unsafe_allow_html=True,
        )
        if room["description"]:
            st.caption(room["description"])
    with head_r:
        if st.button("← 返回房间大厅", use_container_width=True):
            _back_to_lobby()
            return

    # 邀请码一键复制（用只读输入框实现，Streamlit 没有原生复制按钮）
    with st.expander("🔗 邀请同担加入"):
        st.text_input(
            "把下面这段邀请码发给同担",
            value=room["room_code"],
            key=f"invite_code_{room_id}",
            label_visibility="collapsed",
        )
        st.caption(f"当前房间成员（{len(members)} 人）：" + "、".join(m["nickname"] for m in members))

    st.divider()

    # ---------------- 两个标签页 ----------------
    tab_write, tab_timeline = st.tabs(["✍️ 写一段新回忆", "🖼️ 回忆时间线"])

    with tab_write:
        _render_write_form(room_id, user_id)

    with tab_timeline:
        _render_timeline(room_id, user_id)


# ===========================================================================
# 写回忆表单
# ===========================================================================
def _render_write_form(room_id: int, user_id: int) -> None:
    # ---- 第 1 步：基本信息 ----
    title = st.text_input(
        "标题",
        placeholder="例如：散场后我们谁都没走",
        key=f"mem_title_{room_id}",
    )

    content = st.text_area(
        "这段回忆（长日记）",
        placeholder="写多长都可以。哪怕先写一句「好难过」，之后再慢慢补。",
        height=140,
        key=f"mem_content_{room_id}",
    )

    st.markdown("#### 📷 上传照片")
    st.caption(
        f"一次最多 {MAX_PHOTOS_PER_MEMORY} 张，单张不超过 {MAX_UPLOAD_MB}MB。"
        "上传后可以给每张照片写一句注释。"
    )

    # ---- 第 2 步：批量上传 ----
    # 【这里为什么要加 round 计数器？】
    # st.file_uploader 上传的文件会一直留在组件状态里，就算保存成功了，
    # 下次刷新它还在。想"清空已上传的文件"，唯一的办法是换一个新的 key。
    # 所以我们维护一个轮次号，保存成功就 +1，key 一变，上传组件自然重置为空。
    round_key = f"upload_round_{room_id}"
    upload_round = st.session_state.get(round_key, 0)

    # accept_multiple_files=True 就是"一次选几十张"的关键
    uploaded_files = st.file_uploader(
        "选择照片（支持一次多选）",
        type=["jpg", "jpeg", "png", "gif", "webp", "bmp"],
        accept_multiple_files=True,
        key=f"mem_uploads_{room_id}_{upload_round}",
        label_visibility="collapsed",
    )

    # ---- 第 3 步：为每张照片写注释 ----
    # 拼成列表传给 services.create_memory
    photo_payload: list[dict] = []

    if uploaded_files:
        if len(uploaded_files) > MAX_PHOTOS_PER_MEMORY:
            st.error(
                f"选了 {len(uploaded_files)} 张，超过上限 {MAX_PHOTOS_PER_MEMORY} 张，请分批上传。"
            )
        else:
            st.markdown(f"##### 已选 {len(uploaded_files)} 张，给它们配上文字吧")

            # 用两列网格展示，每列一个"缩略图 + 注释输入框"
            cols = st.columns(2, gap="medium")
            for index, uploaded in enumerate(uploaded_files):
                raw = uploaded.getvalue()          # 读到内存里的原始字节
                size_mb = len(raw) / 1024 / 1024

                with cols[index % 2]:
                    # 体积超限的直接跳过，并在界面上标出来
                    if size_mb > MAX_UPLOAD_MB:
                        st.warning(f"「{uploaded.name}」体积 {size_mb:.1f}MB，超过上限，将被跳过")
                        continue

                    st.image(raw, use_container_width=True)

                    # max_chars 会在 UI 层就限制 50 字，后端还会再截断一次（双重保险）
                    caption = st.text_input(
                        f"注释 {index + 1}",
                        max_chars=CAPTION_MAX_LEN,
                        placeholder=f"不超过 {CAPTION_MAX_LEN} 字，例如「最后一首歌的灯海」",
                        key=f"cap_{room_id}_{upload_round}_{index}_{uploaded.name}",
                        label_visibility="collapsed",
                    )

                    photo_payload.append(
                        {"bytes": raw, "name": uploaded.name, "caption": caption}
                    )

    st.write("")
    # ---- 第 4 步：保存 ----
    if st.button("💾 保存这段回忆", type="primary", use_container_width=True):
        if len(uploaded_files or []) > MAX_PHOTOS_PER_MEMORY:
            st.error("照片数量超限，请先减少后再保存。")
            return

        if not title.strip() and not content.strip() and not photo_payload:
            st.warning("至少写个标题，或者传一张照片吧～")
            return

        result = services.create_memory(
            room_id=room_id,
            user_id=user_id,
            title=title.strip() or "无题",
            content=content,
            photos=photo_payload,
        )
        if result.ok:
            st.success(result.message)
            # 清掉输入框里的内容，避免用户误点保存产生重复数据
            for k in [f"mem_title_{room_id}", f"mem_content_{room_id}"]:
                st.session_state.pop(k, None)
            # 轮次 +1 → 上传组件换了新 key → 已上传的照片被清空
            st.session_state[round_key] = upload_round + 1
            st.rerun()
        else:
            st.error(result.message)


# ===========================================================================
# 回忆时间线
# ===========================================================================
def _render_timeline(room_id: int, user_id: int) -> None:
    memories = services.list_memories(room_id, user_id, limit=50)

    if not memories:
        st.info("这间房还空着。切到左边「写一段新回忆」，成为第一个留下记录的人吧。")
        return

    st.caption(f"共 {len(memories)} 段回忆（按时间倒序）")

    for memory in memories:
        # ---- 回忆卡片头部 ----
        created = memory["created_at"]
        time_text = created.strftime("%Y-%m-%d %H:%M") if created else ""

        with st.container():
            st.markdown(
                f"""
                <div class="xh-memory">
                    <h3>{_esc(memory["title"])}</h3>
                    <div class="xh-meta">
                        {_esc(memory["author"])} · {time_text} · {len(memory["photos"])} 张照片
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 日记正文（保留换行的 CSS 已经在 styles.py 里设好了）
            if memory["content"]:
                st.markdown(
                    f'<div class="xh-body">{_esc(memory["content"])}</div>',
                    unsafe_allow_html=True,
                )

            # ---- 照片网格：每行 3 张 ----
            photos = memory["photos"]
            for row_start in range(0, len(photos), 3):
                row_photos = photos[row_start: row_start + 3]
                cols = st.columns(3, gap="small")
                for col, photo in zip(cols, row_photos):
                    with col:
                        # 数据库里只存了路径，这里用绝对路径把文件读出来显示
                        st.image(photo["abs_path"], use_container_width=True)
                        if photo["caption"]:
                            st.markdown(
                                f'<div class="xh-caption">{_esc(photo["caption"])}</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown('<div class="xh-caption">（无注释）</div>',
                                        unsafe_allow_html=True)

            # ---- 只有作者本人能删 ----
            if memory["id"] and _is_mine(memory, user_id):
                confirm_key = f"confirm_del_{memory['id']}"
                if st.session_state.get(confirm_key):
                    c1, c2 = st.columns([1, 5])
                    with c1:
                        if st.button("确认删除", key=f"do_del_{memory['id']}", type="primary"):
                            r = services.delete_memory(memory["id"], user_id)
                            st.session_state.pop(confirm_key, None)
                            st.success(r.message) if r.ok else st.error(r.message)
                            st.rerun()
                    with c2:
                        if st.button("取消", key=f"cancel_del_{memory['id']}"):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                else:
                    if st.button(
                        "🗑 删除这段回忆",
                        key=f"del_{memory['id']}",
                        help="删除后照片文件也会一并清除，不可恢复",
                    ):
                        st.session_state[confirm_key] = True
                        st.rerun()

            st.divider()


def _is_mine(memory: dict, user_id: int) -> bool:
    """判断这篇回忆是不是当前用户写的（用昵称匹配不可靠，这里直接查一次库）

    简单起见，用「作者昵称 == 当前用户昵称」判断会有重名风险，
    所以这里改为查数据库里的 user_id。
    """
    from sqlalchemy import select
    from core.db import get_session
    from core.models import Memory

    with get_session() as db:
        owner_id = db.scalar(select(Memory.user_id).where(Memory.id == memory["id"]))
    return owner_id == user_id


def _back_to_lobby() -> None:
    """返回房间大厅：清掉当前房间状态"""
    st.session_state.pop("current_room_id", None)
    st.session_state.pop("current_room_name", None)
    st.rerun()
