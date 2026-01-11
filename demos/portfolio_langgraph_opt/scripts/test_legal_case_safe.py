#!/usr/bin/env python3
"""
安全测试：验证 legal_case agents 能否正常工作
预算：budget=4（最小），确保不会OOM
"""

import os
import sys
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path("/Users/shenyanran/Dev/AdasDemo/ADAS")
os.chdir(REPO_ROOT)

print("=" * 80)
print("安全测试：Legal Case 优化（Budget=4，最小规模）")
print("=" * 80)

# 1. 验证 legal agents 可加载
print("\n【步骤1】验证 legal agents 加载")
sys.path.insert(0, str(REPO_ROOT))
from demos.portfolio_langgraph_opt.src.agents.load_registry import load_registry

legal_agents_dir = REPO_ROOT / "demos/portfolio_langgraph_opt/src/cases/legal_case/agents"
print(f"Legal agents 目录: {legal_agents_dir}")

try:
    legal_registry = load_registry(str(legal_agents_dir))
    print(f"✅ 成功加载 {len(legal_registry)} 个 legal agents")
    print(f"   Agents: {list(legal_registry.keys())[:5]}...")
except Exception as e:
    print(f"❌ 加载失败: {e}")
    sys.exit(1)

# 2. 测试 search_space 使用 legal registry
print("\n【步骤2】测试 search_space 使用 legal registry")
from demos.portfolio_langgraph_opt.src import search_space

# 暂时 monkey patch 来测试
original_load = search_space.load_registry_cached
def load_legal_registry():
    return legal_registry

search_space.load_registry_cached = load_legal_registry

try:
    candidates = search_space.all_candidates_small()
    print(f"✅ 生成了 {len(candidates)} 个候选拓扑")
    print(f"   第一个: {search_space.candidate_to_name(candidates[0])}")
except Exception as e:
    print(f"❌ 生成失败: {e}")
    search_space.load_registry_cached = original_load
    sys.exit(1)

# 恢复
search_space.load_registry_cached = original_load

# 3. 运行小规模优化（budget=4）
print("\n【步骤3】运行小规模优化测试（Budget=4）")
print("   警告：这将运行实际优化，但规模很小（~1-2分钟）")
print("   这是安全的，不会耗尽内存")

test_output = REPO_ROOT / "demos/portfolio_langgraph_opt/outputs/test_legal_budget4.json"
test_output.parent.mkdir(parents=True, exist_ok=True)

cmd = [
    "python3",
    str(REPO_ROOT / "demos/portfolio_langgraph_opt/portfolio_search.py"),
    "--cases", "demos/portfolio_langgraph_opt/data/cases.jsonl",
    "--policy", "demos/portfolio_langgraph_opt/data/policy_snippets.txt",
    "--mode", "random",
    "--budget", "4",
    "--seed", "42",
    "--out", str(test_output)
]

print(f"   命令: {' '.join(cmd)}")
print("   运行中...")

try:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300  # 5分钟超时
    )
    
    if result.returncode == 0:
        print("✅ 优化成功完成")
        
        # 读取结果
        with open(test_output, 'r') as f:
            results = json.load(f)
        
        print(f"   评估了 {len(results.get('all_scores', []))} 个候选")
        print(f"   最佳候选: {results.get('best', {}).get('candidate_name', 'N/A')}")
        
        # 检查是否有4个点（而不是更多）
        num_candidates = len(results.get('all_scores', []))
        if num_candidates <= 5:
            print(f"✅ 候选数量正常：{num_candidates}")
        else:
            print(f"⚠️  候选数量异常：{num_candidates}（预期≤5）")
    else:
        print(f"❌ 优化失败，退出码: {result.returncode}")
        print("STDOUT:", result.stdout[:500])
        print("STDERR:", result.stderr[:500])
        sys.exit(1)
        
except subprocess.TimeoutExpired:
    print("❌ 超时（5分钟）")
    sys.exit(1)
except Exception as e:
    print(f"❌ 执行失败: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("【关键发现】")
print("=" * 80)
print("问题：portfolio_search.py 使用硬编码的 kyc_case agents")
print("位置：src/agents/load_registry.py:29")
print("      registry_dir = ... / 'kyc_case' / 'agents'")
print("")
print("解决方案：")
print("1. 让 load_registry() 支持传入 case_id")
print("2. 修改 optimize_service.py 传递用户选择的 case_id")
print("3. 修改 portfolio_search.py 接受 --registry-dir 参数")
print("=" * 80)
