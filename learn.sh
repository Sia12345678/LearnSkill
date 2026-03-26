#!/bin/bash
# 学习助手命令行入口

SKILL_DIR="$HOME/.claude/skills/learn"

show_help() {
    echo "📚 学习助手"
    echo ""
    echo "用法: learn [命令] [参数]"
    echo ""
    echo "命令:"
    echo "  (无)           显示主菜单"
    echo "  add <url/书名> 添加学习资料"
    echo "  plan           生成本周计划"
    echo "  status         查看学习状态"
    echo "  dashboard      打开可视化面板"
    echo "  check          检查今日任务"
    echo "  complete <id>  标记任务完成"
    echo "  recommend      查看推荐"
    echo "  sync           同步到GitHub"
    echo "  help           显示此帮助"
    echo ""
    echo "示例:"
    echo "  learn add https://example.com/tutorial"
    echo "  learn plan"
    echo "  learn complete 1 --hours 2.5 --rating 4"
}

case "${1:-}" in
    "")
        python3 "$SKILL_DIR/main.py"
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    "add")
        shift
        python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR')
from main import add_material
add_material(['$@'])
"
        ;;
    "plan")
        python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR')
from main import generate_plan
generate_plan(None)
"
        ;;
    "status")
        python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR')
from main import show_status
show_status(None)
"
        ;;
    "dashboard")
        open "$HOME/Documents/self_learning/learning-assistant/dashboard/index.html"
        ;;
    "check")
        python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR')
from main import check_today_tasks
check_today_tasks(None)
"
        ;;
    "complete")
        shift
        python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR')
from main import complete_task
complete_task(['$@'])
"
        ;;
    "recommend")
        python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR')
from main import show_recommendations
show_recommendations(None)
"
        ;;
    "sync")
        python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR')
from main import sync_to_github
sync_to_github(None)
"
        ;;
    *)
        echo "未知命令: $1"
        show_help
        exit 1
        ;;
esac
