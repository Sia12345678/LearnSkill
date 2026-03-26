"""
学习助手 - 主入口
"""
import os
import sys
import json
import webbrowser
import subprocess
from datetime import date, timedelta
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR, DB_PATH, DASHBOARD_PATH, GITHUB_REPO
from core.db import init_db, get_materials, add_material as db_add_material
from core.db import complete_plan, get_today_tasks, get_statistics
from core.parser import parse_input, parse_obsidian_note
from core.priority import calculate_all_priorities, get_priority_explanation
from core.planner import generate_weekly_plan, get_plan_summary
from core.calendar_sync import sync_week_to_calendar, check_today_completion
from core.evaluator import evaluate_session, get_weekly_report, analyze_learning_patterns
from core.obsidian_sync import sync_to_obsidian, import_from_obsidian
from core.quiz_generator import generate_quiz, generate_stages, save_quiz_to_db, save_stages_to_db


def main(args=None):
    """主菜单"""
    print("=" * 50)
    print("📚 学习助手")
    print("=" * 50)
    print()
    print("可用命令:")
    print("  /learn-add <url/书名>   - 添加学习资料")
    print("  /learn-plan             - 生成本周计划")
    print("  /learn-status           - 查看学习状态")
    print("  /learn-dashboard        - 打开可视化面板")
    print("  /learn-check            - 检查今日任务")
    print("  /learn-complete <id>    - 标记任务完成")
    print("  /learn-sync             - 同步到GitHub")
    print("  /learn-detail <id>      - 查看资料详情(含阶段和测验)")
    print("  /learn-obsidian-sync    - 同步到Obsidian")
    print("  /learn-obsidian-import  - 从Obsidian导入")
    print("  /learn-server           - 启动API服务器(供Dashboard使用)")
    print()

    # 检查初始化
    if not DB_PATH.exists():
        print("首次使用，初始化数据库...")
        init_db()
        print()

    # 显示今日任务
    show_today_tasks()


def add_material(args):
    """添加学习资料"""
    if not args:
        print("用法: /learn-add <url或书名> [--domain <领域>]")
        return

    text = ' '.join(args)

    try:
        parsed = parse_input(text)

        # 计算优先级
        material_id = db_add_material(
            title=parsed['title'],
            url=parsed.get('url'),
            source_type=parsed['source_type'],
            domain=parsed['domain'],
            estimated_hours=parsed['estimated_hours']
        )

        print(f"✓ 已添加学习资料: {parsed['title']}")
        print(f"  类型: {parsed['source_type']}")
        print(f"  领域: {parsed['domain']}")
        print(f"  预估时间: {parsed['estimated_hours']}小时")
        print()

        # 生成阶段计划和测验
        print("正在生成学习阶段和测验...")
        stages = generate_stages(material_id)
        print(f"  已生成 {len(stages)} 个学习阶段")
        save_stages_to_db(material_id, stages)

        # 尝试获取内容并生成测验
        quiz = generate_quiz(material_id)
        if quiz:
            print(f"  已生成 {len(quiz)} 道测验题")
            save_quiz_to_db(material_id, quiz)
        else:
            print("  该资料类型不需要测验")

        # 同步到 Obsidian
        print("正在同步到 Obsidian...")
        sync_to_obsidian(material_id)

        print()

        # 显示优先级分析
        print(get_priority_explanation(material_id))

    except ValueError as e:
        print(f"❌ 错误: {e}")


def generate_plan(args):
    """生成学习计划"""
    from core.planner import generate_weekly_plan as planner_generate

    print("正在生成本周学习计划...")
    print()

    # 生成计划（自动清除旧计划，只安排今天及未来）
    plans = planner_generate(clear_existing=True)

    if not plans:
        print("没有可安排的学习资料，请先添加资料 (/learn-add)")
        return

    # 显示计划
    print(get_plan_summary())
    print()

    # 询问是否同步到Calendar
    print("是否同步到Apple Calendar? (y/n)")
    # 这里简化处理，实际应该读取用户输入
    from datetime import date
    from core.calendar_sync import sync_week_to_calendar
    week_start = date.today() - timedelta(days=date.today().weekday())
    sync_week_to_calendar(week_start)


def show_status(args=None):
    """显示学习状态"""
    stats = get_statistics()

    print("=" * 50)
    print("📊 学习统计")
    print("=" * 50)
    print()

    # 总体统计
    overview = stats.get('overview', {})
    print(f"总资料数: {overview.get('total_materials', 0)}")
    print(f"已完成: {overview.get('completed', 0)}")
    print(f"进行中: {overview.get('in_progress', 0)}")
    print(f"总学习时长: {overview.get('total_hours', 0) or 0:.1f}小时")
    print()

    # 本周统计
    this_week = stats.get('this_week', {})
    print(f"本周学习: {this_week.get('count', 0)}次, {this_week.get('hours', 0) or 0:.1f}小时")
    print()

    # 各领域分布
    print("各领域分布:")
    by_domain = stats.get('by_domain', {})
    for domain, data in by_domain.items():
        print(f"  {domain}: {data['count']}项 ({data['hours'] or 0:.1f}小时)")
    print()

    # 今日任务
    show_today_tasks()


def show_today_tasks():
    """显示今日任务"""
    tasks = get_today_tasks()

    if tasks:
        print("📅 今日学习任务:")
        for task in tasks:
            status = "✓" if task['status'] == 'completed' else "○"
            print(f"  {status} [{task['time_slot']}] {task['title']}")
        print()
    else:
        print("📅 今日无学习任务")
        print()


def open_dashboard(args=None):
    """打开可视化面板"""
    dashboard_file = DASHBOARD_PATH

    if not dashboard_file.exists():
        print("面板文件不存在，正在创建...")
        # 这里应该创建dashboard文件
        create_dashboard_file()

    # 打开浏览器
    webbrowser.open(f"file://{dashboard_file}")
    print(f"✓ 已在浏览器打开: {dashboard_file}")


def create_dashboard_file():
    """创建dashboard文件（从数据项目复制或创建）"""
    # 简化的实现，实际应该从模板创建
    dashboard_file = DASHBOARD_PATH
    dashboard_file.parent.mkdir(parents=True, exist_ok=True)

    html_content = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>学习助手仪表盘</title>
<style>
body{font-family:-apple-system,sans-serif;max-width:1200px;margin:0 auto;padding:20px;background:#1a1a2e;color:#eee}
.card{background:#16213e;border-radius:12px;padding:20px;margin-bottom:20px}
h1{color:#00d4aa}h2{color:#64b5f6;font-size:18px}
.stat{display:inline-block;margin:10px 20px 10px 0;text-align:center}
.stat-value{font-size:28px;color:#00d4aa;font-weight:bold}
.stat-label{font-size:12px;color:#888}
table{width:100%;border-collapse:collapse}
th,td{padding:10px;text-align:left;border-bottom:1px solid #333}
th{color:#64b5f6}
</style></head><body>
<h1>📚 学习助手仪表盘</h1>
<div class="card"><h2>概览</h2>
<div class="stat"><div class="stat-value" id="total">-</div><div class="stat-label">总资料</div></div>
<div class="stat"><div class="stat-value" id="completed">-</div><div class="stat-label">已完成</div></div>
<div class="stat"><div class="stat-value" id="hours">-</div><div class="stat-label">总小时</div></div>
</div>
<div class="card"><h2>本周计划</h2><div id="plan">加载中...</div></div>
<script>
// 这里将从数据库读取数据
fetch('api/stats').then(r=>r.json()).then(data=>{
    document.getElementById('total').textContent=data.total||0;
    document.getElementById('completed').textContent=data.completed||0;
    document.getElementById('hours').textContent=data.hours||0;
});
</script></body></html>"""

    dashboard_file.write_text(html_content)


def check_today_tasks(args=None):
    """检查今日任务完成情况"""
    tasks = check_today_completion()

    if not tasks:
        print("今日Calendar中没有学习事件")
        return

    print("📅 今日学习事件:")
    for task in tasks:
        print(f"  ○ {task['start_time']} {task['title']}")
    print()
    print("请运行 /learn-complete <计划ID> --hours <实际小时> --rating <1-5> 来记录完成情况")


def complete_task(args):
    """标记任务完成（支持记录实际开始和结束时间）"""
    if not args:
        print("用法: /learn-complete <计划ID> --hours <实际小时> --rating <1-5> [--start <开始时间>] [--end <结束时间>]")
        print("  时间格式: HH:MM (24小时制)")
        return

    plan_id = int(args[0])
    actual_hours = None
    rating = None
    start_time = None
    end_time = None

    # 解析参数
    i = 1
    while i < len(args):
        if args[i] == '--hours' and i + 1 < len(args):
            actual_hours = float(args[i + 1])
            i += 2
        elif args[i] == '--rating' and i + 1 < len(args):
            rating = int(args[i + 1])
            i += 2
        elif args[i] == '--start' and i + 1 < len(args):
            start_time = args[i + 1]
            i += 2
        elif args[i] == '--end' and i + 1 < len(args):
            end_time = args[i + 1]
            i += 2
        else:
            i += 1

    if actual_hours is None:
        print("请提供实际学习时长: --hours <小时>")
        return

    rating = rating or 3  # 默认3分

    # 构建时间记录信息
    time_info = f"  实际学习: {actual_hours}小时"
    if start_time and end_time:
        time_info += f" ({start_time} - {end_time})"
    elif start_time:
        time_info += f" (开始: {start_time})"
    elif end_time:
        time_info += f" (结束: {end_time})"

    # 记录完成
    complete_plan(plan_id, actual_hours, rating)

    # 评估
    evaluation = evaluate_session(plan_id, actual_hours, rating)

    print(f"✓ 已记录完成: {evaluation['material_title']}")
    print(time_info)
    print(f"  质量评分: {rating}/5")
    print(f"  效率指数: {evaluation['metrics']['efficiency_index']}")
    print(f"  反馈: {evaluation['feedback']}")


def sync_to_github(args=None):
    """同步到GitHub"""
    print("正在同步到GitHub...")

    # 导出数据库为JSON备份
    from core.evaluator import export_stats_json
    stats_json = export_stats_json()

    backup_file = DATA_DIR / "data" / "stats_backup.json"
    backup_file.write_text(stats_json)

    # Git操作
    try:
        os.chdir(DATA_DIR)

        # 配置git（如果还没配置）
        subprocess.run(['git', 'config', 'user.email', 'learning@assistant.local'], check=False)
        subprocess.run(['git', 'config', 'user.name', 'Learning Assistant'], check=False)

        # 添加、提交、推送
        subprocess.run(['git', 'add', '.'], check=True)
        result = subprocess.run(['git', 'commit', '-m', f'Update: {date.today()}'],
                                capture_output=True, text=True)

        # 推送需要token
        token = os.environ.get('GITHUB_TOKEN')
        if token:
            repo_url = f"https://{token}@github.com/{GITHUB_REPO}.git"
            subprocess.run(['git', 'push', repo_url], check=True)
            print("✓ 已同步到GitHub")
        else:
            print("⚠️ 未设置GITHUB_TOKEN环境变量，无法自动推送")
            print(f"  请手动推送: cd {DATA_DIR} && git push")

    except subprocess.CalledProcessError as e:
        print(f"❌ Git操作失败: {e}")


def start_api_server(args=None):
    """启动 API 服务器（供Dashboard使用）"""
    import subprocess
    api_file = Path(__file__).parent / "api_server.py"

    if not api_file.exists():
        print("❌ API服务器文件不存在")
        return

    print("🚀 启动学习助手API服务器...")
    print("📍 http://localhost:5000")
    print("\n按 Ctrl+C 停止服务器")
    print()

    try:
        subprocess.run([sys.executable, str(api_file)])
    except KeyboardInterrupt:
        print("\n✓ 服务器已停止")


def update_material_progress(args):
    """更新学习资料进度"""
    if not args or len(args) < 2:
        print("用法: /learn-progress <资料ID> <进度百分比> [--hours <已用小时>]")
        return

    material_id = int(args[0])
    progress = int(args[1])
    actual_hours = None

    # 解析参数
    i = 2
    while i < len(args):
        if args[i] == '--hours' and i + 1 < len(args):
            actual_hours = float(args[i + 1])
            i += 2
        else:
            i += 1

    # 更新进度
    from core.db import update_material_progress as db_update_progress
    db_update_progress(material_id, progress, actual_hours)

    print(f"✓ 已更新资料 #{material_id} 进度为 {progress}%")
    if actual_hours:
        print(f"  已用时间: {actual_hours}小时")


def clear_plan(args):
    """清除学习计划"""
    from core.planner import clear_weekly_plan, clear_all_future_plans

    if args and args[0] == '--all':
        print("清除所有未来计划...")
        count = clear_all_future_plans()
        print(f"✓ 已清除 {count} 个未来计划")
    else:
        print("清除本周计划...")
        from datetime import date
        week_start = date.today() - timedelta(days=date.today().weekday())
        count = clear_weekly_plan(week_start)
        print(f"✓ 已清除 {count} 个本周计划")


# 命令映射
def show_material_detail(args):
    """查看资料详情，包括阶段和测验"""
    if not args:
        print("用法: /learn-detail <资料ID>")
        return

    material_id = int(args[0])

    from core.db import get_connection
    with get_connection() as conn:
        cursor = conn.execute('SELECT * FROM materials WHERE id = ?', (material_id,))
        material = cursor.fetchone()

    if not material:
        print(f"❌ 资料 #{material_id} 不存在")
        return

    material_dict = dict(zip([c[0] for c in cursor.description], material))

    print("=" * 50)
    print(f"📚 {material_dict['title']}")
    print("=" * 50)
    print(f"  领域: {material_dict['domain']}")
    print(f"  类型: {material_dict['source_type']}")
    print(f"  预估: {material_dict['estimated_hours']}小时")
    print(f"  进度: {material_dict['progress']}%")
    print()

    import json

    # 显示阶段（从数据库读取）
    with get_connection() as conn:
        cursor = conn.execute(
            'SELECT * FROM learning_stages WHERE material_id = ? ORDER BY stage_number',
            (material_id,)
        )
        stages = cursor.fetchall()

    if stages:
        print("🎯 学习计划阶段:")
        for row in stages:
            stage = dict(zip([c[0] for c in cursor.description], row))
            tasks = json.loads(stage['tasks']) if stage['tasks'] else []
            print(f"\n  阶段{stage['stage_number']+1}: {stage['name']}")
            print(f"    目标: {stage['goal']}")
            print(f"    时长: {stage['estimated_hours']:.1f}小时")
            print(f"    进度: {stage['progress_start']}% - {stage['progress_end']}%")
            if tasks:
                print(f"    任务: {', '.join(tasks[:2])}...")
            print(f"    检查点: {stage['checkpoint']}")
        print()
    else:
        # 如果数据库中没有，动态生成并显示
        stages = generate_stages(material_id)
        if stages:
            print("🎯 学习计划阶段 (动态生成):")
            for i, stage in enumerate(stages, 1):
                print(f"\n  阶段{i}: {stage['name']}")
                print(f"    目标: {stage['goal']}")
                print(f"    时长: {stage['hours']:.1f}小时")
                print(f"    进度: {stage['progress_range'][0]}% - {stage['progress_range'][1]}%")
                print(f"    任务: {', '.join(stage['tasks'][:2])}...")
                print(f"    检查点: {stage['checkpoint']}")
            print()

    # 显示测验
    with get_connection() as conn:
        cursor = conn.execute('SELECT * FROM quizzes WHERE material_id = ? ORDER BY stage', (material_id,))
        quizzes = cursor.fetchall()

    if quizzes:
        print("📝 测验题目:")
        for q in quizzes:
            q_dict = dict(zip([c[0] for c in cursor.description], q))
            print(f"\n  [{q_dict['question_type']}] {q_dict['question'][:60]}...")
            print(f"    难度: {q_dict['difficulty']}")
            if q_dict['hint']:
                print(f"    提示: {q_dict['hint']}")
    else:
        print("  暂无测验题目")
    print()


def sync_obsidian(args=None):
    """同步到 Obsidian"""
    print("正在同步到 Obsidian...")
    success = sync_to_obsidian()
    if success:
        print("✓ 同步完成")
    else:
        print("❌ 同步失败")


def import_obsidian(args=None):
    """从 Obsidian 导入"""
    print("正在从 Obsidian 导入...")
    materials = import_from_obsidian()
    if materials:
        print(f"✓ 发现 {len(materials)} 个新资料")
        for m in materials:
            print(f"  • {m['title']}")
        print("\n运行 /learn-plan 将它们加入学习计划")
    else:
        print("未发现新资料")


COMMANDS = {
    'main': main,
    'add_material': add_material,
    'generate_plan': generate_plan,
    'show_status': show_status,
    'open_dashboard': open_dashboard,
    'check_today_tasks': check_today_tasks,
    'complete_task': complete_task,
    'sync_to_github': sync_to_github,
    'start_server': start_api_server,
    'clear_plan': clear_plan,
    'update_progress': update_material_progress,
    'material_detail': show_material_detail,
    'sync_obsidian': sync_obsidian,
    'import_obsidian': import_obsidian,
}


if __name__ == '__main__':
    # 测试运行
    main()
