-- ============================================================
-- 星海日记 · MySQL 建库脚本
--
-- 用法（命令行）：
--   mysql -u root -p < scripts/init_mysql.sql
--
-- 说明：
--   这个脚本只负责「建库 + 建一个专用账号」。
--   建表的动作交给 Python 的 SQLAlchemy 自动完成（见 scripts/init_db.py），
--   好处是：表结构只在 models.py 里维护一份，不会出现
--   "SQL 文件和 ORM 模型对不上"这种经典翻车场景。
--
--   如果你想用纯 SQL 建表，本项目也提供了完整版（本文件末尾注释部分）。
-- ============================================================

-- 1. 建库
--    utf8mb4 是 MySQL 里唯一能完整存 emoji 的字符集（utf8 只有 3 字节，存不下）
--    utf8mb4_0900_ai_ci 是 MySQL 8.0 的默认排序规则，对中文友好
CREATE DATABASE IF NOT EXISTS xinghai_diary
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_0900_ai_ci;

-- 2. 建专用账号（不要直接用 root 跑应用，这是安全基本盘）
CREATE USER IF NOT EXISTS 'xinghai'@'localhost' IDENTIFIED BY 'xinghai_dev_pwd';

-- 3. 只给这个库的权限，最小权限原则
GRANT ALL PRIVILEGES ON xinghai_diary.* TO 'xinghai'@'localhost';
FLUSH PRIVILEGES;

-- 4. 验证
SELECT '数据库 xinghai_diary 已创建' AS status;
SHOW DATABASES LIKE 'xinghai_diary';

-- ============================================================
-- 附：等价的纯 SQL 建表语句（供参考，正常情况下用不上）
-- ============================================================
/*
USE xinghai_diary;

-- ① 用户表
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE COMMENT '登录名',
    nickname      VARCHAR(50)  NOT NULL        COMMENT '昵称',
    password_hash VARCHAR(255) NOT NULL        COMMENT 'PBKDF2 哈希，绝不存明文',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- ② 房间表
CREATE TABLE IF NOT EXISTS rooms (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    room_code          VARCHAR(32)  NOT NULL UNIQUE COMMENT '邀请码，如 WLG2026',
    room_name          VARCHAR(100) NOT NULL,
    description        VARCHAR(255) NULL,
    join_password_hash VARCHAR(255) NULL COMMENT '可选的加入密码哈希',
    owner_id           INT NULL,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_rooms_room_code (room_code),
    CONSTRAINT fk_rooms_owner FOREIGN KEY (owner_id)
        REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='私密房间';

-- ③ 房间成员表（多对多中间表）
CREATE TABLE IF NOT EXISTS room_members (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    room_id   INT NOT NULL,
    user_id   INT NOT NULL,
    role      VARCHAR(20) NOT NULL DEFAULT 'member',
    joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_room_user (room_id, user_id),
    INDEX ix_rm_room (room_id),
    INDEX ix_rm_user (user_id),
    CONSTRAINT fk_rm_room FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
    CONSTRAINT fk_rm_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='房间成员';

-- ④ 回忆表
CREATE TABLE IF NOT EXISTS memories (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    room_id    INT NOT NULL,
    user_id    INT NOT NULL,
    title      VARCHAR(120) NOT NULL,
    content    TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_memories_room_created (room_id, created_at),
    CONSTRAINT fk_mem_room FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
    CONSTRAINT fk_mem_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='一段回忆/一篇日记';

-- ⑤ 照片表
CREATE TABLE IF NOT EXISTS photos (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    memory_id     INT NOT NULL,
    file_path     VARCHAR(255) NOT NULL COMMENT '相对 uploads/ 的路径',
    original_name VARCHAR(255) NULL,
    caption       VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '≤50 字注释',
    sort_order    INT NOT NULL DEFAULT 0,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_photos_memory (memory_id),
    CONSTRAINT fk_photo_memory FOREIGN KEY (memory_id)
        REFERENCES memories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='照片';
*/
