# 🌌 星海日记 · 赛博回忆档案馆

> 把散场的夜晚，装进一间不会关灯的房间。

面向追星粉丝的**私密回忆日记工具**。第一批 MVP：创建私密房间 → 批量上传演唱会照片 → 每张照片写 ≤50 字注释 → 写一段长日记 → 时间线回看。

**版权红线**：本项目不内置任何官方图片、音乐、视频。平台只是一块空白的「U 盘 + 日记本」，所有内容全部由用户自行上传，且仅房间成员可见。

---

## 一、快速开始（3 步）

### 方式 A：Windows 一键启动

双击项目根目录的 **`启动.bat`** 即可。它会自动装依赖 → 建表 → 灌演示数据 → 打开浏览器。

### 方式 B：手动启动

```bash
# 1. 安装依赖（国内建议加镜像源，直连 pypi.org 会很慢）
pip install -i https://mirrors.cloud.tencent.com/pypi/simple/ -r requirements.txt

# 2. 初始化数据库（建表 + 演示数据；可重复执行）
python scripts/init_db.py --demo

# 3. 启动
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

**演示账号**（执行过 `--demo` 才有）：

| 项目 | 值 |
|---|---|
| 用户名 | `demo` |
| 密码 | `demo123` |
| 房间邀请码 | `WLG2026` |

---

## 二、数据库怎么设计（5 张表）

### 关系图

```
users ──< room_members >── rooms
  │                          │
  └──────< memories >────────┘
              │
           < photos >
```

### ① `users` — 用户

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INT PK | 主键 |
| `username` | VARCHAR(50) UNIQUE | 登录名 |
| `nickname` | VARCHAR(50) | 展示给同担看的昵称 |
| `password_hash` | VARCHAR(255) | **PBKDF2 哈希，绝不存明文** |
| `created_at` | DATETIME | 注册时间 |

### ② `rooms` — 私密房间

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INT PK | |
| `room_code` | VARCHAR(32) UNIQUE | 邀请码，如 `WLG2026` |
| `room_name` | VARCHAR(100) | 房间名 |
| `description` | VARCHAR(255) | 一句话简介 |
| `join_password_hash` | VARCHAR(255) NULL | **可选的加入密码**（光靠邀请码不够私密） |
| `owner_id` | INT FK→users | 房主 |
| `created_at` | DATETIME | |

### ③ `room_members` — 房间成员（多对多中间表）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INT PK | |
| `room_id` | INT FK→rooms | CASCADE 删除 |
| `user_id` | INT FK→users | CASCADE 删除 |
| `role` | VARCHAR(20) | `owner` / `member` |
| `joined_at` | DATETIME | |
| | | **UNIQUE(room_id, user_id)** ← 防重复加入 |

> 为什么不在 `users` 里直接放 `room_id`？因为一个人会加入多个房间（王力宏、周杰伦、毕业回忆…）。这是数据库里最典型的**多对多关系**。

### ④ `memories` — 一段回忆 / 一篇日记

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INT PK | |
| `room_id` | INT FK→rooms | 归属房间 |
| `user_id` | INT FK→users | 作者 |
| `title` | VARCHAR(120) | 标题 |
| `content` | TEXT | 长日记，不限长度 |
| `created_at` | DATETIME | |

> 索引 `(room_id, created_at)`：因为「读某房间的回忆、按时间倒序」是最高频查询。

### ⑤ `photos` — 照片

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INT PK | |
| `memory_id` | INT FK→memories | CASCADE 删除 |
| `file_path` | VARCHAR(255) | **相对路径**，如 `12/a1b2c3.jpg` |
| `original_name` | VARCHAR(255) | 原始文件名，纯展示 |
| `caption` | VARCHAR(50) | **每张照片的注释，≤50 字** |
| `sort_order` | INT | 保持上传顺序 |
| `created_at` | DATETIME | |

> **照片为什么不存进数据库？** 图片体积大，塞进去会让备份和查询双双变慢。业界做法是「文件进磁盘/对象存储，数据库只存路径」。这里就是 `photos.file_path` 指向 `uploads/` 下的真实文件。

---

## 三、已实现的功能

- [x] **用户认证** — 注册 / 登录 / 退出，PBKDF2-HMAC-SHA256 加盐哈希（26 万次迭代）
- [x] **私密房间** — 创建房间（可自定义邀请码）、邀请码加入（大小写不敏感）、可选加入密码
- [x] **权限隔离** — 每个读写操作前都校验成员身份，非成员看不到任何内容
- [x] **批量上传照片** — 一次最多 50 张，白名单校验后缀、限制单张体积
- [x] **照片注释** — 每张照片 ≤50 字，UI 和后端双重限制
- [x] **长日记** — 不限长度的整体总结
- [x] **回忆时间线** — 按时间倒序展示，照片三列网格 + 注释
- [x] **删除回忆** — 仅作者可删，照片文件与数据库记录级联清理
- [x] **房间统计** — 成员数 / 回忆数（单条 SQL JOIN + GROUP BY，避免 N+1 查询）

### 架构分层

```
ui/        ← 界面层（Streamlit）：只管画和收，不写 SQL
   ↓
core/services.py  ← 业务层：权限校验、事务、文件存储
   ↓
core/db.py + core/models.py  ← 数据层：SQLAlchemy ORM
   ↓
SQLite / MySQL
```

> 分层的好处：将来从 Streamlit 换成「FastAPI + 小程序」，`core/` 这一整层可以**原封不动复用**，只重写 `ui/`。

---

## 四、项目结构

```
xinghai-diary/
├── app.py                    # 入口：页面路由 + 侧边栏
├── core/
│   ├── config.py             # 配置：数据库连接串、上传目录、业务常量
│   ├── models.py             # 5 张表的 ORM 定义
│   ├── db.py                 # 引擎 / 会话 / 建表
│   ├── auth.py               # 密码哈希、注册、登录
│   └── services.py           # 房间 / 回忆 / 照片的业务逻辑
├── ui/
│   ├── styles.py             # 全局 CSS
│   ├── page_auth.py          # 登录 / 注册页
│   ├── page_rooms.py         # 房间大厅
│   └── page_memory.py        # 房间内部：发回忆 + 时间线
├── scripts/
│   ├── init_db.py            # 建表脚本（--demo 灌演示数据）
│   ├── init_mysql.sql        # MySQL 建库脚本
│   ├── smoke_test.py         # 后端端到端冒烟测试
│   └── ui_test.py            # 界面层测试（Streamlit AppTest）
├── uploads/                  # 照片落盘目录（不进 git）
├── requirements.txt
├── .env.example
├── .gitattributes            # 统一换行符，避免跨平台警告
├── 启动.bat                  # 一键启动
└── 推送到GitHub.bat          # 一键推送到 GitHub
```

---

## 五、切换到 MySQL

项目通过 SQLAlchemy 同时支持 SQLite 和 MySQL，**切换只改一行配置**。

```bash
# 1. 建库 + 建专用账号（不要用 root 跑应用）
mysql -u root -p < scripts/init_mysql.sql

# 2. 复制配置文件
cp .env.example .env

# 3. 编辑 .env，取消注释并改成你的账号密码
# DATABASE_URL=mysql+pymysql://xinghai:xinghai_dev_pwd@127.0.0.1:3306/xinghai_diary?charset=utf8mb4
```

> `charset=utf8mb4` **必须带**，否则中文和 emoji 会乱码或直接报错。
> 密码里含 `@` `:` `/` 等特殊字符时需要 URL 编码（`@` → `%40`）。

改完直接 `streamlit run app.py`，SQLAlchemy 会连 MySQL 并自动建表，代码零改动。

---

## 六、测试

项目自带两套自动化测试，改完代码跑一遍就知道有没有搞坏东西。

```bash
# ① 后端主链路（45 项断言）
python scripts/smoke_test.py

# ② 界面层（用 Streamlit 官方 AppTest，无头跑真实交互）
python scripts/ui_test.py
```

**`smoke_test.py` 覆盖**：注册/登录/密码哈希落库 → 建房/加房/邀请码大小写/加入密码 → 发回忆/传照片/注释自动截断到 50 字 → 时间线读取 → 权限隔离（非成员读不到任何内容）→ 级联删除 → 测试数据自动清理。

**`ui_test.py` 覆盖**：登录页渲染 → 错误密码提示 → 正确登录进大厅 → 进入房间看看板 → 返回大厅，每一步都断言"页面没有抛异常"。

> 为什么要测两遍？因为后端对 ≠ 界面能跑。比如我曾写错一个统计 SQL，接口能返回数据但成员数永远是 1；也有界面参数调用错误只有真跑一遍才暴露。两层都测，才能安心交付。

---

## 七、推送到 GitHub

本地仓库已经初始化好并完成了首次提交（分支 `main`，23 个文件）。推送分两步：

### 1. 在浏览器创建一个空仓库

打开 <https://github.com/new>：

- Repository name 填 **`xinghai-diary`**
- 私有 / 公开随你
- **不要**勾选 `Add a README file`、`.gitignore`、`license`（否则会有历史冲突，还得先 pull）

### 2. 推送

双击项目根目录的 **`推送到GitHub.bat`**，它会自动配好远程地址并推送。

或者手动执行：

```bash
git remote add origin git@github.com:wke-engineer/xinghai-diary.git
git branch -M main
git push -u origin main
```

> ⚠️ **注意**：这台机器上 `github.com:443`（网页/HTTPS）是被网络阻断的（连接超时），
> 但 `api.github.com:443` 和 `git@github.com:22`（SSH）是通的。
> **所以必须用 SSH 推送，不要用 HTTPS。** 网页操作（建仓库）请在浏览器里做。

### 推送排障

| 现象 | 原因 | 解决 |
|---|---|---|
| `Permission denied (publickey)` | 公钥没加到 GitHub | 把 `~/.ssh/id_ed25519.pub` 的内容贴到 GitHub → Settings → SSH and GPG keys |
| `Connection timed out` / 卡住不动 | 22 端口被网络封了 | 改用 443 端口，见下方配置 |
| `remote origin already exists` | 重复添加远程 | `git remote remove origin` 后重试 |
| `failed to push some refs` | 远程仓库不是空的 | 删掉远程仓库重建，或先 `git pull --rebase origin main` |

**22 端口被封时，改用 SSH over 443**：编辑 `~/.ssh/config`（没有就新建），加入：

```
Host github.com
    HostName ssh.github.com
    Port 443
    User git
```

改完用 `ssh -T git@github.com` 验证，看到 `Hi xxx! You've successfully authenticated` 就成了。

---

## 八、技术选型说明

| 层 | 选型 | 为什么 |
|---|---|---|
| 前端 | Streamlit | 纯 Python 写网页，不需要学 HTML/JS，MVP 阶段出结果最快 |
| ORM | SQLAlchemy 2.0 | 换数据库不用改业务代码；参数化查询天然防 SQL 注入 |
| 数据库 | SQLite → MySQL | 本地零配置验证；SQLAlchemy 让两者切换成本几乎为零 |
| 密码 | hashlib PBKDF2 | 标准库自带，无第三方依赖；加盐 + 26 万次迭代抗暴力破解 |
| 图片 | 磁盘文件 + DB 存路径 | 体积大的东西不进数据库 |

---

## 九、后续路线（按周）

| 阶段 | 目标 |
|---|---|
| Week 1 ✅ | Streamlit + 数据库跑通：上传照片、写注释和日记、保存、回看（**本仓库已完成**） |
| Week 2 | 房间体系增强：邀请链接、成员管理、房主踢人 |
| Week 3 | 接入大模型 API：① 根据照片生成温柔应援文案；② 短文本扩写成 100 字小作文 |
| Week 4 | 一键生成回忆册（长图 / PDF） |
| 之后 | FastAPI 后端 + 微信小程序前端（`core/` 层直接复用） |

---

## 十、合规声明

- 项目不含任何官方图片、音乐、视频、艺人物料。
- 所有内容由用户自行上传，仅房间内成员可见。
- 用户注册即承诺只上传自己拥有版权的素材。
- 本条为产品红线，任何后续功能都不得突破。
