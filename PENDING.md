# XDFManager MCP 待修复问题清单

> 记录工具层与原子脚本之间的参数不匹配问题
> 创建日期: 2026-06-29
> 更新日期: 2026-06-30

---

## ✅ 已修复并归档的问题

### 1. `create_class` (班课建档) - ✅ FIXED
**问题**: 缺少两个必需参数 `first_class_date`, `students`

| MCP工具参数 | 原子脚本参数 | 状态 |
|------------|-------------|:----:|
| `class_name` | `--class-name` | ✅ 匹配 |
| `course_type` | `--course-type` | ✅ 匹配 |
| `schedule_type` | `--schedule-type` | ✅ 匹配 |
| `first_class_date` | `--first-class-date` | ✅ **已修复** |
| `students` | `--students` | ✅ **已修复** |

**验证结果**: 2026-06-30 测试通过

---

### 2. `create_one_on_one` (一对一建档) - ✅ FIXED
**问题**: 缺少必需参数 `first_class_date`, `schedule_type`

| MCP工具参数 | 原子脚本参数 | 状态 |
|------------|-------------|:----:|
| `student_name` | `--student` | ✅ 映射正确 |
| `course_type` | `--course-type` | ✅ 匹配 |
| `schedule_type` | `--schedule-type` | ✅ **已修复** |
| `first_class_date` | `--first-class-date` | ✅ **已修复** |

**验证结果**: 2026-06-30 测试通过

---

### 3. `create_class_lesson` 参数映射 - ✅ FIXED
**问题**: `lesson_num` vs `--lesson` 参数名不匹配

| MCP工具参数 | 原子脚本参数 | 状态 |
|------------|-------------|:----:|
| `target` | `--target` | ✅ 匹配 |
| `dates` | `--dates` | ✅ 匹配 |
| `time_slots` | `--time-slots` | ✅ 匹配 |

**验证结果**: 2026-06-30 测试通过

---

## 🔴 未修复问题

### 4. `create_test_feedback` - ❌ 严重不匹配
**问题**: MCP 工具定义了 5 个参数，但原子脚本只支持 3 个

| MCP工具参数 | 原子脚本参数 | 状态 |
|------------|-------------|:----:|
| `target` | `--target` | ✅ 匹配 |
| `test_name` | `--test-name` | ✅ 匹配 |
| `date` | `--date` | ✅ 匹配 |
| `student` | ❌ | 🔴 **原子脚本不支持** |
| `content` | ❌ | 🔴 **原子脚本不支持** |

**错误信息**:
```
create_test_feedback.py: error: unrecognized arguments: --student 艾克丹 --content 测试反馈内容
```

**需要决策**:
- [ ] 方案A: 修改原子脚本 `create/create_test_feedback.py`，增加 `--student` 和 `--content` 参数
- [ ] 方案B: 修改 MCP 工具定义，移除 `student` 和 `content` 参数（仅创建测试文件夹，不写入内容）

---

### 5. 原子脚本的 `sys.path` 配置问题 - 🔴 严重
**问题**: 多个原子脚本通过 `subprocess` 调用时找不到 `xdf_utils` 模块

**受影响脚本**:
```
scripts/search/find_lesson_files.py
scripts/create/create_test_feedback.py
scripts/extract/extract_raw.py
scripts/extract/extract_feedback.py
scripts/extract/extract_content.py
scripts/write/write_feedback.py
scripts/write/write_raw.py
scripts/write/write_teaching_content.py
```

**问题表现**:
```python
# 脚本第 13-20 行
from xdf_utils import (
    resolve_vault,
    resolve_target,
    ...
)
# ModuleNotFoundError: No module named 'xdf_utils'
```

**根本原因**:
1. 脚本直接 `from xdf_utils import ...`，但没有在开头添加 `sys.path.insert(0, ...)`
2. 工作流通过 `subprocess.run` 调用子脚本时，子进程的 `sys.path` 是全新的
3. 子进程不知道父目录在哪里，找不到 `xdf_utils.py`

**修复建议**:
在每个原子脚本开头添加（参考 `daily_feedback_generator.py` 第 24 行）:
```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

或在 `_run_script` 函数中设置 `PYTHONPATH` 环境变量:
```python
def _run_script(script_rel_path, **kwargs):
    ...
    env = os.environ.copy()
    env["PYTHONPATH"] = SCRIPTS_DIR + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=SCRIPTS_DIR,
        encoding="utf-8", errors="replace", env=env
    )
```

---

### 6. `schedule_type` 值描述不一致 - 🟡 轻微
**问题**: MCP 工具描述与原子脚本接受的值不匹配

| 位置 | 值 |
|------|-----|
| MCP 工具描述 | `weekend` / `weekday` |
| 原子脚本实际接受 | `weekend` / `full-time` |

**影响**: 按文档传入 `weekday` 时，可能不符合预期
**建议**: 统一 MCP 工具描述为 `weekend` / `full-time`

---

### 7. Write/Extract 工具参数名不一致 - 🟡 轻微
**问题**: 不同工具的参数命名风格不统一

| 工具 | 参数 |
|------|------|
| `write_feedback` | `lesson`, `student` |
| `write_raw` | `lesson`, `student` |
| `write_teaching_content` | `lesson` |
| `extract_content` | `lesson` |
| `create_class_lesson` | `dates`, `time_slots` |

**建议**: 统一使用 `lesson_num` 或 `lesson`，保持一致性

---

## 修复优先级 (更新)

1. **🔴 紧急**: 原子脚本 `sys.path` 配置问题（影响所有子进程调用）
2. **🔴 紧急**: `create_test_feedback` - 确定方案并修复参数不匹配
3. **🟡 中等**: `schedule_type` 值描述统一
4. **🟢 轻微**: Write/Extract 工具参数名统一

---

## 测试记录

| 日期 | 测试项目 | 结果 |
|------|---------|------|
| 2026-06-30 | `create_class` 参数修复 | ✅ 通过 |
| 2026-06-30 | `create_one_on_one` 参数修复 | ✅ 通过 |
| 2026-06-30 | `create_class_lesson` 参数映射 | ✅ 通过 |
| 2026-06-30 | `create_test_feedback` 完整调用 | ❌ 失败 |
| 2026-06-30 | `generate_daily_feedback` 工作流 | ❌ 失败（`sys.path` 问题） |
