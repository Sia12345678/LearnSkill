"""
数据库操作模块 - SQLite
"""
import sqlite3
import json
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# 处理相对导入
try:
    from ..config import DB_PATH, DATA_DIR, DEFAULT_PROFICIENCY
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import DB_PATH, DATA_DIR, DEFAULT_PROFICIENCY


def init_db():
    """初始化数据库"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    schema_path = DATA_DIR / "data" / "schema.sql"
    if schema_path.exists():
        with sqlite3.connect(DB_PATH) as conn:
            with open(schema_path) as f:
                conn.executescript(f.read())
        print(f"✓ 数据库初始化完成: {DB_PATH}")
    else:
        # 如果schema.sql不存在，创建基础结构
        _create_base_schema()

    # 初始化用户画像
    _init_user_profile()


def _create_base_schema():
    """创建基础数据库结构"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT,
                source_type TEXT NOT NULL,  -- 'video', 'book', 'course', 'article', 'github'
                domain TEXT NOT NULL,       -- 'work-ai', 'dsml', 'quant', 'philosophy', 'literature', 'physics'
                status TEXT DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed'
                priority_score REAL DEFAULT 0,
                estimated_hours REAL,
                actual_hours REAL DEFAULT 0,
                progress INTEGER DEFAULT 0,  -- 0-100
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                content_summary TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start DATE NOT NULL,
                material_id INTEGER NOT NULL,
                planned_hours REAL NOT NULL,
                scheduled_date DATE NOT NULL,
                time_slot TEXT NOT NULL,    -- 'weekend_morning', 'weekend_afternoon', 'weekday_evening'
                status TEXT DEFAULT 'scheduled',  -- 'scheduled', 'completed', 'postponed'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (material_id) REFERENCES materials(id)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER,
                material_id INTEGER NOT NULL,
                actual_start TIMESTAMP NOT NULL,
                actual_end TIMESTAMP,
                actual_hours REAL,
                completion_rate REAL DEFAULT 0,  -- 0.0-1.0
                quality_rating INTEGER,  -- 1-5 用户自评
                notes TEXT,
                FOREIGN KEY (plan_id) REFERENCES plans(id),
                FOREIGN KEY (material_id) REFERENCES materials(id)
            );

            CREATE TABLE IF NOT EXISTS user_profile (
                domain TEXT PRIMARY KEY,
                proficiency INTEGER DEFAULT 5,  -- 1-10
                avg_time_ratio REAL DEFAULT 1.0,  -- 实际/预估时间比
                preferred_slot TEXT,
                last_studied DATE,
                total_hours REAL DEFAULT 0,
                completed_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT,
                source_type TEXT,
                domain TEXT,
                reason TEXT,
                status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL,
                stage INTEGER NOT NULL,
                question TEXT NOT NULL,
                question_type TEXT,
                difficulty TEXT,
                hint TEXT,
                answer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (material_id) REFERENCES materials(id)
            );

            CREATE TABLE IF NOT EXISTS learning_stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL,
                stage_number INTEGER NOT NULL,
                name TEXT NOT NULL,
                goal TEXT,
                tasks TEXT,  -- JSON array
                checkpoint TEXT,
                progress_start INTEGER,
                progress_end INTEGER,
                estimated_hours REAL,
                FOREIGN KEY (material_id) REFERENCES materials(id)
            );

            CREATE TABLE IF NOT EXISTS intervention_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,  -- 'started_early', 'progress_updated', 'task_substituted', 'time_changed'
                original_plan_id INTEGER,
                new_plan_id INTEGER,
                user_choice TEXT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (material_id) REFERENCES materials(id),
                FOREIGN KEY (original_plan_id) REFERENCES plans(id),
                FOREIGN KEY (new_plan_id) REFERENCES plans(id)
            );
        ''')


def _init_user_profile():
    """初始化用户画像"""
    with sqlite3.connect(DB_PATH) as conn:
        for domain, proficiency in DEFAULT_PROFICIENCY.items():
            conn.execute('''
                INSERT OR IGNORE INTO user_profile (domain, proficiency)
                VALUES (?, ?)
            ''', (domain, proficiency))


def get_connection():
    """获取数据库连接"""
    if not DB_PATH.exists():
        init_db()
    return sqlite3.connect(DB_PATH)


# === 资料操作 ===

def add_material(title: str, url: Optional[str], source_type: str, domain: str,
                 estimated_hours: float, priority_score: float = 0,
                 content_summary: str = "") -> int:
    """添加学习资料"""
    with get_connection() as conn:
        cursor = conn.execute('''
            INSERT INTO materials (title, url, source_type, domain,
                                   estimated_hours, priority_score, content_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, url, source_type, domain, estimated_hours, priority_score, content_summary))
        return cursor.lastrowid


def get_materials(status: Optional[str] = None, domain: Optional[str] = None) -> List[Dict]:
    """获取资料列表"""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM materials WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        query += " ORDER BY priority_score DESC, created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def update_material_progress(material_id: int, progress: int, actual_hours: Optional[float] = None):
    """更新资料进度"""
    with get_connection() as conn:
        if progress >= 100:
            conn.execute('''
                UPDATE materials
                SET progress = ?, status = 'completed', completed_at = ?,
                    actual_hours = COALESCE(?, actual_hours)
                WHERE id = ?
            ''', (progress, datetime.now(), actual_hours, material_id))
        elif progress > 0:
            conn.execute('''
                UPDATE materials
                SET progress = ?, status = 'in_progress', started_at = COALESCE(started_at, ?),
                    actual_hours = COALESCE(?, actual_hours)
                WHERE id = ?
            ''', (progress, datetime.now(), actual_hours, material_id))


# === 计划操作 ===

def create_plan(week_start: date, material_id, planned_hours: float,
                scheduled_date: date, time_slot: str,
                material_title: str = None, material_domain: str = None, material_url: str = None) -> int:
    """创建学习计划

    Args:
        week_start: 周开始日期
        material_id: 可以是 int（从数据库） 或 str/key（从 MD 文件索引）
        planned_hours: 计划时长
        scheduled_date: 计划日期
        time_slot: 时间段
        material_title: 资料标题
        material_domain: 资料领域
        material_url: 资料链接
    """
    with get_connection() as conn:
        db_material_id = None

        # 如果有 material_id 且是数字，从数据库查找
        if isinstance(material_id, int):
            db_material_id = material_id
        elif isinstance(material_id, str):
            # 尝试查找现有的 material
            existing = conn.execute(
                'SELECT id FROM materials WHERE title = ?',
                (material_id,)
            ).fetchone()
            if existing:
                db_material_id = existing[0]

        cursor = conn.execute('''
            INSERT INTO plans (week_start, material_id, material_title, material_domain, material_url,
                             planned_hours, scheduled_date, time_slot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (week_start, db_material_id, material_title, material_domain, material_url,
              planned_hours, scheduled_date, time_slot))
        return cursor.lastrowid


def get_weekly_plan(week_start: date) -> List[Dict]:
    """获取本周计划"""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''
            SELECT id, material_title as title, material_domain as domain, material_url as url,
                   planned_hours, scheduled_date, time_slot, status
            FROM plans
            WHERE week_start = ?
            ORDER BY scheduled_date, time_slot
        ''', (week_start,)).fetchall()
        return [dict(row) for row in rows]


def get_today_tasks() -> List[Dict]:
    """获取今日任务"""
    today = date.today()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''
            SELECT id, material_title as title, material_domain as domain, material_url as url,
                   planned_hours, scheduled_date, time_slot, status
            FROM plans
            WHERE scheduled_date = ? AND status = 'scheduled'
        ''', (today,)).fetchall()
        return [dict(row) for row in rows]


def complete_plan(plan_id: int, actual_hours: float, quality_rating: int, notes: str = ""):
    """完成计划任务"""
    with get_connection() as conn:
        # 更新计划状态
        conn.execute('''
            UPDATE plans SET status = 'completed' WHERE id = ?
        ''', (plan_id,))

        # 获取material_id
        plan = conn.execute('SELECT material_id FROM plans WHERE id = ?', (plan_id,)).fetchone()
        if plan:
            material_id = plan[0]
            # 创建学习记录
            conn.execute('''
                INSERT INTO sessions (plan_id, material_id, actual_start, actual_end,
                                     actual_hours, quality_rating, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (plan_id, material_id, datetime.now(), datetime.now(),
                  actual_hours, quality_rating, notes))


# === 用户画像操作 ===

def get_user_profile() -> Dict[str, Dict]:
    """获取用户画像"""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM user_profile').fetchall()
        return {row['domain']: dict(row) for row in rows}


def update_domain_proficiency(domain: str, proficiency: int):
    """更新领域熟练度"""
    with get_connection() as conn:
        conn.execute('''
            UPDATE user_profile SET proficiency = ? WHERE domain = ?
        ''', (proficiency, domain))


def update_learning_stats(domain: str, actual_hours: float, time_ratio: float):
    """更新学习统计"""
    with get_connection() as conn:
        conn.execute('''
            UPDATE user_profile
            SET total_hours = total_hours + ?,
                completed_count = completed_count + 1,
                avg_time_ratio = (avg_time_ratio * completed_count + ?) / (completed_count + 1),
                last_studied = ?
            WHERE domain = ?
        ''', (actual_hours, time_ratio, date.today(), domain))


# === 推荐操作 ===

def add_recommendation(title: str, url: str, source_type: str, domain: str, reason: str) -> int:
    """添加待审批推荐"""
    with get_connection() as conn:
        cursor = conn.execute('''
            INSERT INTO recommendations (title, url, source_type, domain, reason)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, url, source_type, domain, reason))
        return cursor.lastrowid


def get_pending_recommendations() -> List[Dict]:
    """获取待审批推荐"""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''
            SELECT * FROM recommendations WHERE status = 'pending'
            ORDER BY created_at DESC
        ''').fetchall()
        return [dict(row) for row in rows]


def approve_recommendation(rec_id: int):
    """审批通过推荐"""
    with get_connection() as conn:
        rec = conn.execute('''
            SELECT * FROM recommendations WHERE id = ?
        ''', (rec_id,)).fetchone()
        if rec:
            # 添加到materials
            add_material(
                title=rec['title'],
                url=rec['url'],
                source_type=rec['source_type'],
                domain=rec['domain'],
                estimated_hours=0  # 需要后续评估
            )
            # 更新推荐状态
            conn.execute('''
                UPDATE recommendations SET status = 'approved', reviewed_at = ?
                WHERE id = ?
            ''', (datetime.now(), rec_id))


# === 统计操作 ===

def get_statistics() -> Dict:
    """获取学习统计"""
    with get_connection() as conn:
        stats = {}

        # 总体统计
        row = conn.execute('''
            SELECT
                COUNT(*) as total_materials,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                SUM(actual_hours) as total_hours
            FROM materials
        ''').fetchone()
        stats['overview'] = {
            'total_materials': row[0] if row else 0,
            'completed': row[1] if row else 0,
            'in_progress': row[2] if row else 0,
            'total_hours': row[3] if row else 0
        }

        # 本周完成
        week_start = date.today() - timedelta(days=date.today().weekday())
        row = conn.execute('''
            SELECT COUNT(*) as count, SUM(actual_hours) as hours
            FROM sessions
            WHERE actual_start >= ?
        ''', (week_start,)).fetchone()
        stats['this_week'] = {
            'count': row[0] if row and row[0] else 0,
            'hours': row[1] if row and row[1] else 0
        }

        # 各领域分布
        rows = conn.execute('''
            SELECT domain, COUNT(*) as count, SUM(actual_hours) as hours
            FROM materials
            GROUP BY domain
        ''').fetchall()
        stats['by_domain'] = {row[0]: {'count': row[1], 'hours': row[2]} for row in rows}

        return stats


# === 数据库迁移 ===

def migrate_db():
    """数据库迁移 - 添加新字段"""
    with get_connection() as conn:
        # 检查并添加 sessions.intervention_type
        try:
            conn.execute('SELECT intervention_type FROM sessions LIMIT 1')
        except sqlite3.OperationalError:
            conn.execute('ALTER TABLE sessions ADD COLUMN intervention_type TEXT DEFAULT "planned"')
            conn.execute('ALTER TABLE sessions ADD COLUMN replaced_plan_id INTEGER')
            print("✓ 已添加 sessions.intervention_type 字段")

        # 检查并添加 plans.intervened
        try:
            conn.execute('SELECT intervened FROM plans LIMIT 1')
        except sqlite3.OperationalError:
            conn.execute('ALTER TABLE plans ADD COLUMN intervened BOOLEAN DEFAULT 0')
            conn.execute('ALTER TABLE plans ADD COLUMN intervention_reason TEXT')
            print("✓ 已添加 plans.intervened 字段")

        conn.commit()


# === 干预日志操作 ===

def log_intervention(material_id: int, action_type: str, original_plan_id: Optional[int] = None,
                     new_plan_id: Optional[int] = None, user_choice: str = "", reason: str = "") -> int:
    """记录干预日志"""
    with get_connection() as conn:
        cursor = conn.execute('''
            INSERT INTO intervention_log (material_id, action_type, original_plan_id, new_plan_id, user_choice, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (material_id, action_type, original_plan_id, new_plan_id, user_choice, reason))
        return cursor.lastrowid


def get_intervention_logs(material_id: Optional[int] = None, limit: int = 50) -> List[Dict]:
    """获取干预日志"""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        query = '''
            SELECT l.*, m.title as material_title
            FROM intervention_log l
            JOIN materials m ON l.material_id = m.id
        '''
        params = []
        if material_id:
            query += ' WHERE l.material_id = ?'
            params.append(material_id)
        query += ' ORDER BY l.created_at DESC LIMIT ?'
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


# === 计划干预操作 ===

def substitute_task(original_plan_id: int, new_material_id: int, new_planned_hours: float,
                    reason: str = "") -> tuple:
    """替换任务：将原计划推迟一周，创建新计划

    Returns:
        (new_plan_id, postponed_plan_id)
    """
    from datetime import timedelta

    with get_connection() as conn:
        # 获取原 plan 信息
        original = conn.execute(
            'SELECT * FROM plans WHERE id = ?', (original_plan_id,)
        ).fetchone()
        if not original:
            raise ValueError(f"Plan {original_plan_id} not found")

        original_dict = dict(zip([c[0] for c in original.description], original))

        # 1. 标记原 plan 为 postponed，并记录干预
        conn.execute('''
            UPDATE plans SET status = 'postponed', intervened = 1, intervention_reason = ?
            WHERE id = ?
        ''', (f"被替换为资料#{new_material_id}: {reason}", original_plan_id))

        # 2. 推迟原任务一周（创建新的 plan）
        new_scheduled_date = date.fromisoformat(original_dict['scheduled_date']) + timedelta(days=7)
        cursor = conn.execute('''
            INSERT INTO plans (week_start, material_id, planned_hours, scheduled_date, time_slot, status, intervened)
            VALUES (?, ?, ?, ?, ?, 'scheduled', 1)
        ''', (
            new_scheduled_date - timedelta(days=new_scheduled_date.weekday()),
            original_dict['material_id'],
            original_dict['planned_hours'],
            new_scheduled_date,
            original_dict['time_slot']
        ))
        postponed_plan_id = cursor.lastrowid

        # 3. 创建新的 plan 记录今日任务
        today = date.today()
        cursor = conn.execute('''
            INSERT INTO plans (week_start, material_id, planned_hours, scheduled_date, time_slot, status, intervened)
            VALUES (?, ?, ?, ?, ?, 'scheduled', 1)
        ''', (
            today - timedelta(days=today.weekday()),
            new_material_id,
            new_planned_hours,
            today,
            original_dict['time_slot']
        ))
        new_plan_id = cursor.lastrowid

        # 4. 记录干预日志
        log_intervention(
            material_id=new_material_id,
            action_type='task_substituted',
            original_plan_id=original_plan_id,
            new_plan_id=new_plan_id,
            user_choice='substitute',
            reason=reason
        )

        conn.commit()
        return (new_plan_id, postponed_plan_id)


def postpone_plan(plan_id: int, days: int = 7, reason: str = "") -> int:
    """推迟计划指定天数，默认一周

    Returns:
        新的 plan_id
    """
    with get_connection() as conn:
        plan = conn.execute('SELECT * FROM plans WHERE id = ?', (plan_id,)).fetchone()
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        plan_dict = dict(zip([c[0] for c in plan.description], plan))

        # 标记原 plan 为 postponed
        conn.execute('''
            UPDATE plans SET status = 'postponed', intervened = 1, intervention_reason = ?
            WHERE id = ?
        ''', (f"推迟{days}天: {reason}", plan_id))

        # 创建新的 plan
        new_date = date.fromisoformat(plan_dict['scheduled_date']) + timedelta(days=days)
        cursor = conn.execute('''
            INSERT INTO plans (week_start, material_id, planned_hours, scheduled_date, time_slot, status, intervened)
            VALUES (?, ?, ?, ?, ?, 'scheduled', 1)
        ''', (
            new_date - timedelta(days=new_date.weekday()),
            plan_dict['material_id'],
            plan_dict['planned_hours'],
            new_date,
            plan_dict['time_slot']
        ))
        new_plan_id = cursor.lastrowid

        conn.commit()
        return new_plan_id


def create_spontaneous_session(material_id: int, actual_start: datetime,
                                actual_end: datetime, actual_hours: float,
                                quality_rating: int, progress_delta: int = 0) -> int:
    """创建自发学习记录（无计划）"""
    with get_connection() as conn:
        cursor = conn.execute('''
            INSERT INTO sessions (plan_id, material_id, actual_start, actual_end,
                                 actual_hours, quality_rating, intervention_type)
            VALUES (NULL, ?, ?, ?, ?, ?, 'spontaneous')
        ''', (material_id, actual_start, actual_end, actual_hours, quality_rating))

        # 记录干预日志
        log_intervention(
            material_id=material_id,
            action_type='started_early',
            user_choice='spontaneous',
            reason=f"自发学习 {actual_hours}小时, 进度+{progress_delta}%"
        )

        # 更新资料进度
        if progress_delta > 0:
            current = conn.execute('SELECT progress FROM materials WHERE id = ?', (material_id,)).fetchone()
            new_progress = min(100, (current[0] if current else 0) + progress_delta)
            conn.execute('''
                UPDATE materials SET progress = ?, status = 'in_progress',
                    started_at = COALESCE(started_at, ?)
                WHERE id = ?
            ''', (new_progress, actual_start, material_id))

        conn.commit()
        return cursor.lastrowid


# === 预估时间计算 ===

def calculate_remaining_hours(material_id: int) -> float:
    """根据进度和已用时间，计算预估剩余时间

    公式: 剩余时间 = (已用时间 / 当前进度%) * (100% - 当前进度%)
    如果进度为0，返回原始预估时间
    """
    with get_connection() as conn:
        row = conn.execute('''
            SELECT estimated_hours, actual_hours, progress
            FROM materials WHERE id = ?
        ''', (material_id,)).fetchone()

        if not row:
            return 0

        estimated, actual, progress = row

        if progress == 0 or not actual:
            # 未开始或没有实际用时记录，返回原始预估
            return estimated or 2.0

        if progress >= 100:
            return 0

        # 计算效率：实际用时 / 进度 = 每1%进度需要多少小时
        hours_per_percent = actual / progress
        remaining_percent = 100 - progress
        remaining_hours = hours_per_percent * remaining_percent

        return round(remaining_hours, 1)


def update_material_remaining_estimate(material_id: int) -> float:
    """更新资料的预估时间为剩余时间，返回新预估"""
    remaining = calculate_remaining_hours(material_id)
    with get_connection() as conn:
        conn.execute('''
            UPDATE materials SET estimated_hours = ? WHERE id = ?
        ''', (remaining, material_id))
    return remaining


# === 资源进度操作（资源总览页） ===

def _make_resource_key(title: str, domain: str) -> str:
    """生成资源唯一标识"""
    return f"{title}|{domain}"


def add_to_progress(title: str, domain: str, url: str = None, estimated_hours: float = 0) -> int:
    """将资源加入进程记录"""
    resource_key = _make_resource_key(title, domain)
    with get_connection() as conn:
        # 检查是否已存在
        existing = conn.execute(
            'SELECT id FROM resource_progress WHERE resource_key = ?',
            (resource_key,)
        ).fetchone()

        if existing:
            return existing[0]  # 已存在，返回现有ID

        cursor = conn.execute('''
            INSERT INTO resource_progress (resource_key, title, domain, url, estimated_hours, progress, status)
            VALUES (?, ?, ?, ?, ?, 0, 'active')
        ''', (resource_key, title, domain, url, estimated_hours))
        return cursor.lastrowid


def get_progress_list() -> List[Dict]:
    """获取所有进程记录"""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''
            SELECT * FROM resource_progress
            ORDER BY updated_at DESC
        ''').fetchall()
        return [dict(row) for row in rows]


def get_progress_by_key(resource_key: str) -> Optional[Dict]:
    """根据资源key获取进程记录"""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            'SELECT * FROM resource_progress WHERE resource_key = ?',
            (resource_key,)
        ).fetchone()
        return dict(row) if row else None


def update_progress(resource_key: str, progress: int, actual_hours: float = None) -> bool:
    """更新资源进度"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if actual_hours is not None:
            cursor.execute('''
                UPDATE resource_progress
                SET progress = ?, actual_hours = ?, status = ?, updated_at = ?
                WHERE resource_key = ?
            ''', (
                progress,
                actual_hours,
                'completed' if progress >= 100 else 'active',
                datetime.now(),
                resource_key
            ))
        else:
            cursor.execute('''
                UPDATE resource_progress
                SET progress = ?, status = ?, updated_at = ?
                WHERE resource_key = ?
            ''', (
                progress,
                'completed' if progress >= 100 else 'active',
                datetime.now(),
                resource_key
            ))
        conn.commit()
        return cursor.rowcount > 0


def remove_from_progress(resource_key: str) -> bool:
    """从进程记录中移除"""
    with get_connection() as conn:
        conn.execute('DELETE FROM resource_progress WHERE resource_key = ?', (resource_key,))
        return True


def is_in_progress(resource_key: str) -> bool:
    """检查资源是否已在进程中"""
    with get_connection() as conn:
        row = conn.execute(
            'SELECT id FROM resource_progress WHERE resource_key = ?',
            (resource_key,)
        ).fetchone()
        return row is not None
