"""
config.py —— 全局配置模块

【为什么要单独抽一个配置文件？】
如果把数据库密码、上传目录这些写死在各个业务代码里，将来想把项目
从 SQLite 换成 MySQL、从本地换成云服务器，就要满项目找、逐个改，非常容易漏。
所以统一放在这里：改配置只改这一个地方（或改 .env 文件），业务代码一行都不用动。

【读取优先级】
.env 文件里的值  >  代码里的默认值
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 1. 路径基准
# ---------------------------------------------------------------------------
# __file__ 是当前文件 core/config.py 的路径
# .resolve() 转成绝对路径，.parent 取上一层目录（core/），再 .parent 就是项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 把项目根目录下的 .env 文件读进来，注入到系统环境变量中。
# 如果 .env 不存在，load_dotenv 会安静地跳过，不会报错。
load_dotenv(BASE_DIR / ".env")


# ---------------------------------------------------------------------------
# 2. 数据库连接串
# ---------------------------------------------------------------------------
# DATABASE_URL 支持两种驱动，格式参考 SQLAlchemy 官方规范：
#
#   SQLite（默认，零配置、数据存在单个文件里，最适合本地 MVP）
#     sqlite:///C:/path/to/xinghai.db
#
#   MySQL（生产/学习用，需要在 .env 里显式写出来）
#     mysql+pymysql://用户名:密码@127.0.0.1:3306/xinghai_diary?charset=utf8mb4
#     注意 charset=utf8mb4：否则中文和 emoji 会存成乱码或报错
#
# 默认走 SQLite，保证任何人 clone 下来都能立刻跑起来，不需要先装数据库。
DEFAULT_SQLITE_URL = f"sqlite:///{(BASE_DIR / 'xinghai.db').as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)

# 判断当前用的是不是 SQLite —— 建引擎时需要用不同的参数（见 db.py）
IS_SQLITE = DATABASE_URL.startswith("sqlite")


# ---------------------------------------------------------------------------
# 3. 照片存储
# ---------------------------------------------------------------------------
# 照片以「文件」形式落盘，数据库里只存相对路径。
# 为什么不把图片二进制塞进数据库？图片体积大，塞进去会让数据库备份/查询变慢。
# 业界常规做法：文件进对象存储/磁盘，数据库只存路径（就是下面 photos.file_path）。
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))

# 单张照片体积上限（单位 MB）
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))

# 一次可以批量上传多少张（需求里说"一次性上传几十张"）
MAX_PHOTOS_PER_MEMORY = int(os.getenv("MAX_PHOTOS_PER_MEMORY", "50"))


# ---------------------------------------------------------------------------
# 4. 业务规则常量
# ---------------------------------------------------------------------------
# 每张照片下面的注释上限（需求明确要求不超过 50 字）
CAPTION_MAX_LEN = 50

# 允许上传的图片后缀（白名单，安全考虑：防止有人上传 .exe 伪装成图片）
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# 应用标题（界面上展示）
APP_NAME = "星海日记"
APP_SLOGAN = "把散场的夜晚，装进一间不会关灯的房间"

# 确保上传目录一定存在（第一次运行时自动创建）
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
