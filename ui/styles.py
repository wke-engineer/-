"""
styles.py —— 全局视觉样式（CSS 注入）

Streamlit 原生长得比较"工程师化"，我们通过注入一段 CSS 把它调成
偏文艺、偏回忆感的风格：柔和渐变、圆角卡片、留白更舒服。

【怎么注入？】st.markdown(css, unsafe_allow_html=True) 会把这段样式塞进页面。
只要调用一次（在 app.py 开头），全局生效。
"""

import streamlit as st

# 主题色统一放在这里，改一处全站生效
PRIMARY = "#6C5CE7"       # 星海紫
ACCENT = "#FD79A8"        # 应援粉
TEXT = "#1F2233"          # 主文字（浅色主题用深字）
MUTED = "#6B7280"         # 次要文字
BG = "#FFFFFF"

_GLOBAL_CSS = f"""
<style>
/* ---------- 全局字体与背景 ---------- */
html, body, [class*="css"] {{
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
}}

.stApp {{
    background:
        radial-gradient(1200px 600px at 12% -10%, #F3EFFF 0%, rgba(243,239,255,0) 60%),
        radial-gradient(900px 500px at 95% 0%, #FFF0F6 0%, rgba(255,240,246,0) 55%),
        #FFFFFF;
}}

/* 收窄主内容区，阅读更舒服 */
.block-container {{
    padding-top: 2.2rem;
    padding-bottom: 4rem;
    max-width: 1080px;
}}

/* ---------- 隐藏 Streamlit 默认装饰 ---------- */
#MainMenu, footer {{ visibility: hidden; }}

/* ---------- 标题 ---------- */
.xh-hero {{
    text-align: center;
    padding: 1.6rem 1rem 1.2rem 1rem;
    margin-bottom: 0.6rem;
}}
.xh-hero h1 {{
    font-size: 2.3rem;
    font-weight: 800;
    letter-spacing: 2px;
    margin: 0 0 .5rem 0;
    background: linear-gradient(100deg, {PRIMARY} 0%, {ACCENT} 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}
.xh-hero p {{
    color: {MUTED};
    font-size: .98rem;
    margin: 0;
    letter-spacing: .5px;
}}

/* ---------- 通用卡片 ---------- */
.xh-card {{
    background: #FFFFFF;
    border: 1px solid #EDEBF5;
    border-radius: 16px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 1rem;
    box-shadow: 0 2px 14px rgba(108, 92, 231, .06);
}}

.xh-memory {{
    background: #FFFFFF;
    border: 1px solid #EDEBF5;
    border-left: 4px solid {PRIMARY};
    border-radius: 14px;
    padding: 1.1rem 1.3rem .4rem 1.3rem;
    margin-bottom: 1.3rem;
    box-shadow: 0 2px 16px rgba(108, 92, 231, .07);
}}
.xh-memory h3 {{
    margin: 0 0 .35rem 0;
    font-size: 1.18rem;
    color: {TEXT};
}}
.xh-meta {{
    color: {MUTED};
    font-size: .82rem;
    margin-bottom: .7rem;
}}
.xh-body {{
    color: {TEXT};
    font-size: .96rem;
    line-height: 1.85;
    white-space: pre-wrap;
    margin-bottom: .5rem;
}}

/* 照片注释 */
.xh-caption {{
    color: {MUTED};
    font-size: .84rem;
    line-height: 1.5;
    padding: .3rem .1rem .8rem .1rem;
    min-height: 2rem;
}}

/* ---------- 房间卡片 ---------- */
.xh-room {{
    background: linear-gradient(135deg, #FBFAFF 0%, #F7F5FF 100%);
    border: 1px solid #E8E4F8;
    border-radius: 14px;
    padding: .95rem 1.1rem;
    margin-bottom: .8rem;
}}
.xh-room .t {{ font-weight: 700; color: {TEXT}; font-size: 1.02rem; }}
.xh-room .s {{ color: {MUTED}; font-size: .8rem; margin-top: .25rem; }}

/* ---------- 徽标 ---------- */
.xh-chip {{
    display: inline-block;
    background: #F1EEFF;
    color: {PRIMARY};
    border-radius: 999px;
    padding: .16rem .68rem;
    font-size: .74rem;
    font-weight: 600;
    margin-right: .35rem;
}}
.xh-chip.pink {{ background: #FFEFF5; color: #D6338A; }}

/* ---------- 按钮微调 ---------- */
.stButton > button {{
    border-radius: 10px;
    font-weight: 600;
    transition: all .18s ease;
}}
.stButton > button:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(108,92,231,.22);
}}

/* 主按钮用品牌渐变 */
.stButton > button[kind="primary"] {{
    background: linear-gradient(100deg, {PRIMARY} 0%, #8E7BF0 100%);
    border: none;
    color: #fff;
}}

/* ---------- 输入框 ---------- */
.stTextInput input, .stTextArea textarea {{
    border-radius: 10px !important;
}}

/* ---------- 侧边栏 ---------- */
section[data-testid="stSidebar"] {{
    background: #FBFAFF;
    border-right: 1px solid #EFECF8;
}}

/* ---------- 标签页 ---------- */
.stTabs [data-baseweb="tab-list"] {{ gap: .4rem; }}
.stTabs [data-baseweb="tab"] {{
    border-radius: 10px 10px 0 0;
    padding: .5rem 1.1rem;
}}
</style>
"""


def inject() -> None:
    """把全局样式注入页面（在 app.py 里调用一次即可）"""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    """渲染顶部大标题区"""
    st.markdown(
        f'<div class="xh-hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )
