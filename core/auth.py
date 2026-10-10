"""
auth.py —— 用户认证模块（注册 / 登录 / 密码安全）

【安全铁律：数据库里永远不存明文密码】
本模块用 PBKDF2-HMAC-SHA256（Python 标准库 hashlib 自带，无需第三方依赖）来做密码哈希。

流程是这样的：
    注册时：明文密码 + 随机盐  -->  哈希  -->  存进数据库（形如 pbkdf2_sha256$260000$盐$哈希）
    登录时：用户输入的密码 + 数据库里的盐  -->  同样算法哈希  -->  和数据库里的哈希比对

为什么这样是安全的？
    1. 哈希不可逆：拿到哈希值也算不出原密码。
    2. 加盐（salt）：即使两个用户密码一模一样，因为盐不同，存的哈希也完全不同，
       黑客无法用"彩虹表"批量破解。
    3. 迭代次数（260000 次）：故意让每次计算变慢（约几十毫秒），
       这样暴力枚举密码的成本会高到不现实。但对正常登录只慢几十毫秒，用户无感。
"""

import hashlib
import hmac
import os
import re
from dataclasses import dataclass

from sqlalchemy import select

from core.db import get_session
from core.models import User

# ---- 算法参数 --------------------------------------------------------------
_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 260_000        # 迭代次数，越大越安全但越慢，26 万是当前推荐量级
_SALT_BYTES = 16             # 盐的长度（字节）

# ---- 用户名规则 ------------------------------------------------------------
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


@dataclass
class AuthResult:
    """统一的认证结果对象。

    为什么不用 True/False？因为失败时还要知道"为什么失败"，好给用户提示。
    ok       —— 是否成功
    message  —— 给用户看的提示文案
    user     —— 成功时带上 User 对象
    """
    ok: bool
    message: str
    user: User | None = None


# ===========================================================================
# 密码哈希 / 校验
# ===========================================================================
def hash_password(password: str, salt: bytes | None = None) -> str:
    """把明文密码转成可安全入库的哈希字符串。

    返回格式： pbkdf2_sha256$260000$<盐的十六进制>$<哈希的十六进制>
    把算法和迭代次数一起存进去，将来想升级算法，老密码也还能验证。
    """
    if salt is None:
        # os.urandom 是密码学安全的随机数生成器，每个用户一个独一无二的盐
        salt = os.urandom(_SALT_BYTES)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),   # 密码转字节
        salt,
        _ITERATIONS,
    )
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码是否正确。

    原理：把用户输入的密码，用"数据库里存的那个盐 + 那套参数"重新算一遍哈希，
    再和数据库里的哈希比对。因为盐是随机的，所以只能重算，不能反推。
    """
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != _ALGORITHM:
            return False

        recalculated = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        ).hex()
    except (ValueError, AttributeError):
        # 数据库里的哈希串格式不对（比如被人工改坏了），直接判定失败，不要抛异常
        return False

    # hmac.compare_digest 是"恒定时间比较"：
    # 普通的 == 会在第一个不同的字符处提前返回，攻击者能通过响应时间差猜出密码。
    # 用这个函数，无论对不对，耗时都一样，堵住"时序攻击"这条路。
    return hmac.compare_digest(recalculated, digest_hex)


# ===========================================================================
# 注册
# ===========================================================================
def register(username: str, nickname: str, password: str) -> AuthResult:
    """注册新用户"""
    username = (username or "").strip()
    nickname = (nickname or "").strip() or username

    # ---- 输入校验（永远不要相信前端传过来的数据）----
    if not _USERNAME_RE.match(username):
        return AuthResult(False, "用户名需为 3-20 位字母、数字或下划线")
    if len(password) < 6:
        return AuthResult(False, "密码至少 6 位")
    if len(nickname) > 50:
        return AuthResult(False, "昵称太长（最多 50 字）")

    with get_session() as db:
        # 先查重。虽然数据库有 unique 约束兜底，但提前查一下能给出友好提示，
        # 而不是让用户看到一串 IntegrityError 的报错堆栈。
        exists = db.scalar(select(User).where(User.username == username))
        if exists:
            return AuthResult(False, "该用户名已被注册")

        user = User(
            username=username,
            nickname=nickname,
            password_hash=hash_password(password),   # 注意：存的是哈希，不是 password
        )
        db.add(user)
        db.flush()      # flush 会立刻执行 INSERT，从而拿到自增的 user.id（此时还没 commit）
        return AuthResult(True, "注册成功", user)


# ===========================================================================
# 登录
# ===========================================================================
def login(username: str, password: str) -> AuthResult:
    """登录校验"""
    username = (username or "").strip()
    if not username or not password:
        return AuthResult(False, "请输入用户名和密码")

    with get_session() as db:
        user = db.scalar(select(User).where(User.username == username))

        # 【安全细节】用户不存在 和 密码错误 返回同一句提示。
        # 如果分别提示"用户不存在"/"密码错误"，攻击者就能靠这个来批量探测哪些用户名是有效的。
        if user is None or not verify_password(password, user.password_hash):
            return AuthResult(False, "用户名或密码错误")

        return AuthResult(True, "登录成功", user)


# ===========================================================================
# 改密码（顺手提供，方便后续扩展）
# ===========================================================================
def change_password(user_id: int, old_password: str, new_password: str) -> AuthResult:
    if len(new_password) < 6:
        return AuthResult(False, "新密码至少 6 位")

    with get_session() as db:
        user = db.get(User, user_id)
        if user is None:
            return AuthResult(False, "用户不存在")
        if not verify_password(old_password, user.password_hash):
            return AuthResult(False, "原密码不正确")

        user.password_hash = hash_password(new_password)
        return AuthResult(True, "密码已更新")
