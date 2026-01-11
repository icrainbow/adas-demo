# 硬编码全面审计报告

## 执行时间
2026-01-11

## 审计范围
- Python核心逻辑文件
- 服务层（API、配置、优化）
- 前端（UI和Viz）
- 测试文件
- 配置文件

---

## 🟢 可接受的硬编码（合理的默认值/常量）

### 1. 配置文件中的路径（配置层面，易于修改）

#### `config/run.yaml`
```yaml
cases_path: demos/portfolio_langgraph_opt/data/cases.jsonl
policy_path: demos/portfolio_langgraph_opt/data/policy_snippets.txt
output_dir: demos/portfolio_langgraph_opt/runs
```
**评估**: ✅ **可接受** - 这是配置文件，用户可以直接修改
**用途**: 为CLI和API提供默认路径

#### `src/cases/_default.yaml`
```yaml
default_case_id: "kyc_case"
```
**评估**: ✅ **可接受** - 合理的默认值，易于修改
**用途**: 系统启动时的默认case选择

### 2. 服务器配置

#### `service/api_server.py`
```python
def start_server(port=8080):
```
**评估**: ✅ **可接受** - 提供了参数化接口，可通过命令行参数覆盖
**示例**: `python -m service.api_server 9000`

### 3. 安全限制常量

#### `service/limits.py`
```python
MAX_BUDGET = 32
MAX_SAMPLES = 6
MAX_UPLOAD_MB = 1
MAX_AGENT_YAML_KB = 100
TIMEOUT_SECONDS = 3600
```
**评估**: ✅ **可接受** - 安全限制常量，集中定义，便于维护
**建议**: 考虑将这些移到配置文件以便运维调整（低优先级）

### 4. 评估权重默认值

#### `src/evaluate.py` 中的环境变量fallback
```python
coverage_weight = float(os.getenv("PORTFOLIO_COVERAGE_WEIGHT", "100.0"))
violation_penalty = float(os.getenv("PORTFOLIO_VIOLATION_PENALTY", "200.0"))
complexity_penalty = float(os.getenv("PORTFOLIO_COMPLEXITY_PENALTY", "0.5"))
```
**评估**: ✅ **优秀设计** - 支持环境变量覆盖，同时有合理的默认值

---

## 🟡 可改进的硬编码（当前可行，但有优化空间）

### 1. 项目路径前缀

**位置**: 多个文件中
```python
"demos/portfolio_langgraph_opt/..."
```

**影响文件**:
- `portfolio_search.py` (3处)
- `service/api_server.py` (13处)
- `service/optimize_service.py` (4处)
- `service/config_loader.py` (8处)
- `src/search_space_generator.py` (2处)
- 所有verify脚本 (2-4处每个)

**当前问题**:
- 如果项目重命名或移动位置，需要修改多处
- 测试文件中也有这些路径

**建议改进方案** (优先级: 中):

#### 方案A: 使用项目根目录动态计算
```python
# 在一个中心位置定义
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent  # 从当前文件向上找
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
OUTPUT_DIR = PROJECT_ROOT / "runs"
```

#### 方案B: 环境变量
```python
PROJECT_ROOT = os.getenv("PORTFOLIO_PROJECT_ROOT", "demos/portfolio_langgraph_opt")
```

**影响**: 需要修改约10-15个文件，工作量中等，但收益明显

---

### 2. UI中的默认输入路径

#### `ui/config.html`
```html
<input type="text" id="casesPath" value="demos/portfolio_langgraph_opt/data/cases.jsonl" />
```

**问题**: HTML中硬编码路径
**建议**: 通过API `/api/config/defaults` 动态获取
**优先级**: 低（用户可以手动修改输入框）

---

### 3. Viz回退路径

#### `viz/app.js` - loadCandidatesManifest()
```javascript
const paths = [
    '../artifacts/candidates_manifest.json',
    './artifacts/candidates_manifest.json',
    'artifacts/candidates_manifest.json'
];
```

**当前状态**: 已经为results实现了API动态加载，但manifest仍然硬编码
**建议**: 添加 `/api/artifacts/manifest` 端点
**优先级**: 低（manifest是可选功能）

---

## 🔴 需要修复的硬编码（当前无）

✅ **没有发现严重的硬编码问题！**

之前的 `legal_demo.json` 硬编码已经被修复，现在使用 `/api/results/latest` 动态查找。

---

## 📊 硬编码分类统计

| 类型 | 数量 | 状态 | 优先级 |
|------|------|------|--------|
| 配置文件路径 | ~30 | 🟢 可接受/🟡 可优化 | 中 |
| 端口号 | 2 | 🟢 可接受 | 低 |
| 安全限制常量 | 5 | 🟢 可接受 | 低 |
| Case/Agent IDs | 0 | 🟢 已动态化 | N/A |
| UI路径 | 2 | 🟡 可优化 | 低 |
| 数据文件路径 | ~15 | 🟡 可优化 | 中 |

---

## 🎯 重构建议优先级

### 高优先级 (无)
当前无高优先级重构需求。

### 中优先级

#### 1. 集中化项目路径管理
**收益**: 提高代码可维护性，便于项目迁移
**工作量**: 中等（约2-3小时）
**影响范围**: ~15个文件

**实现方案**:
```python
# 新增: src/paths.py
from pathlib import Path
import os

_this_file = Path(__file__).resolve()
PROJECT_ROOT = _this_file.parent.parent  # demos/portfolio_langgraph_opt

# 数据路径
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_CASES_PATH = DATA_DIR / "cases.jsonl"
DEFAULT_POLICY_PATH = DATA_DIR / "policy_snippets.txt"

# 输出路径
OUTPUT_DIR = PROJECT_ROOT / "runs"
VIZ_DIR = PROJECT_ROOT / "viz"

# 配置路径
CONFIG_DIR = PROJECT_ROOT / "config"
EVAL_CONFIG_PATH = CONFIG_DIR / "eval.yaml"
RUN_CONFIG_PATH = CONFIG_DIR / "run.yaml"

# Case和Agent路径
CASES_ROOT = PROJECT_ROOT / "src" / "cases"

def get_case_dir(case_id: str) -> Path:
    """Get the directory for a specific case."""
    return CASES_ROOT / case_id

def get_agents_dir(case_id: str) -> Path:
    """Get the agents directory for a specific case."""
    return get_case_dir(case_id) / "agents"
```

然后在所有文件中替换硬编码路径:
```python
# 之前
cases_path = "demos/portfolio_langgraph_opt/data/cases.jsonl"

# 之后
from src.paths import DEFAULT_CASES_PATH
cases_path = str(DEFAULT_CASES_PATH)
```

### 低优先级

#### 2. API动态配置端点
添加 `/api/config/paths` 返回所有路径配置，让UI完全不需要硬编码路径。

#### 3. 配置文件化安全限制
将 `limits.py` 中的常量移到 `config/limits.yaml`，便于运维调整。

---

## 🔍 代码质量观察

### 优秀实践 ✅

1. **环境变量支持**: `evaluate.py` 支持通过环境变量覆盖所有权重
2. **API动态加载**: `/api/results/latest` 动态查找最新结果
3. **YAML驱动**: Case和Agent使用YAML配置而非代码逻辑
4. **参数化接口**: 大多数函数接受路径参数，不强制默认值
5. **集中式限制**: 安全限制集中在 `limits.py` 中

### 可改进之处 ⚠️

1. **路径重复**: "demos/portfolio_langgraph_opt" 字符串出现约40次
2. **相对路径**: 一些地方使用相对路径 `../` ，一些使用绝对路径
3. **测试文件路径**: 测试中也硬编码了路径，应该使用fixtures或helper函数

---

## 📝 重构路线图（可选）

如果需要进一步优化，建议按以下顺序:

### Phase 1: 集中化路径管理 (2-3小时)
- 创建 `src/paths.py`
- 重构所有Python文件使用集中路径
- 更新测试文件

### Phase 2: API配置端点 (1小时)
- 添加 `/api/config/paths` 端点
- 更新UI使用API获取路径

### Phase 3: 配置文件化限制 (30分钟)
- 创建 `config/limits.yaml`
- 更新 `limits.py` 读取配置文件

### Phase 4: 文档和测试 (1小时)
- 更新文档说明新的路径管理方式
- 添加路径解析的单元测试

**总工作量估计**: 4.5-5.5小时

---

## 🏆 总体评价

**当前状态**: 🟢 **良好**

系统已经很好地避免了业务逻辑硬编码:
- ✅ Case和Agent完全动态化
- ✅ 搜索空间YAML驱动
- ✅ 结果文件动态查找
- ✅ 支持环境变量配置

主要的"硬编码"集中在：
- 项目路径前缀（可通过集中管理改进）
- 配置文件中的默认值（这是合理的）

**是否需要立即重构**: ❌ **不需要**

当前系统已经足够灵活和可扩展。建议的重构是"nice-to-have"而非"必须"，可以在以下情况下考虑:
1. 需要将项目重命名或移动位置
2. 需要支持多个独立部署实例
3. 代码维护变得困难时

**扩展性评分**: 8.5/10
- 业务逻辑扩展性: 10/10 ⭐
- 部署灵活性: 7/10
- 配置可维护性: 8/10

