# 主动响应项目模块说明（V1）

本文档对应 `G:\1.7b` 当前代码版本，说明每个模块的功能、核心接口和边界。

## 1. 架构总览

项目按“数据结构 -> 上下文管理 -> 意图评分 -> 时机决策 -> 主流程编排 -> 演示与测试”分层：

1. `active_response/domain.py`：统一领域对象定义  
2. `active_response/config.py`：运行配置  
3. `active_response/context_buffer.py`：对话上下文缓存  
4. `active_response/intent_engine.py`：意图识别与评分接口  
5. `active_response/timing_policy.py`：响应时机规则  
6. `active_response/response_manager.py`：待响应任务管理  
7. `active_response/pipeline.py`：端到端主流程编排  
8. `scripts/run_demo.py`：本地演示入口  
9. `tests/test_pipeline.py`：最小行为测试  
10. `active_response/__init__.py`：包导出入口

---

## 2. 模块逐项说明

### 2.1 `active_response/domain.py`
**功能**：定义系统内统一的数据结构（dataclass），避免模块间“字典字段名漂移”。

**核心对象**：
- `Utterance`：一条 ASR 语句（`utterance_id/speaker_id/text/start_ms/end_ms`）
- `IntentResult`：意图评分结果（`score/should_respond/reason/draft_reply`）
- `PendingResponse`：待播报任务（`plan_time_ms/response/score/source_utt_id`）
- `DecisionEvent`：最终决策事件（`event_type/event_time_ms/...`）

**关键约束**：
- `Utterance.__post_init__` 校验 `start_ms <= end_ms`。

---

### 2.2 `active_response/config.py`
**功能**：集中定义 V1 运行参数。

**核心对象**：
- `V1Config`
  - `urgency_threshold`：触发阈值（默认 `0.7`）
  - `wait_ms`：响应等待窗（默认 `800`）
  - `context_window_ms`：上下文窗口（默认 `10000`）
  - `max_pending_per_speaker`：每个说话人最多挂起任务（默认 `1`）

---

### 2.3 `active_response/context_buffer.py`
**功能**：维护全局对话时间线，并按时间窗口返回上下文。

**核心类**：
- `ContextBuffer`

**核心方法**：
- `add_utterance(utt)`：写入语句，并按 `end_ms` 保持有序。
- `recent_context(current_end_ms, window_ms)`：返回最近窗口内的全体语句。
- `recent_by_speaker(speaker_id, current_end_ms, window_ms)`：返回某个说话人的窗口语句。

**用途**：
- 给意图模型提供“多路历史上下文”。

---

### 2.4 `active_response/intent_engine.py`
**功能**：定义意图评分接口，并提供可运行的规则基线实现。

**核心接口**：
- `IntentEngine.score(context, current_utt) -> IntentResult`
- `BaseIntentEngine`（抽象基类）

**默认实现**：
- `RuleBasedIntentEngine`
  - 车控类关键词 -> 高分（倾向触发）
  - 闲聊类关键词 -> 低分（不触发）
  - 请求提示词 -> 中间分
  - 返回 `score + should_respond + reason + draft_reply`

**边界说明**：
- 当前实现是 V1 baseline，后续可无缝替换为 Qwen/微调模型，只要保持 `score(...)` 契约不变。

---

### 2.5 `active_response/timing_policy.py`
**功能**：封装响应时机的最小规则。

**核心函数**：
- `plan_time(end_ms, wait_ms)`：计算计划播报时刻。
- `is_interrupted(next_start_ms, planned_time_ms)`：判断是否被后续发言打断。

**规则**：
- 若 `next_start_ms < planned_time_ms` 则判定 `interrupted`。

---

### 2.6 `active_response/response_manager.py`
**功能**：管理 pending 响应任务（按说话人维度）。

**核心类**：
- `ResponseManager`

**核心方法**：
- `add_or_replace_pending(pending)`：同 speaker 保留最新任务（V1 策略）。
- `discard_pending(speaker_id)`：丢弃挂起任务。
- `merge_pending(speaker_id, supplement)`：把补充内容并入已有任务文本。
- `get_pending/all_pending`：查询挂起任务。

**用途**：
- 支持后续“补充约束（merge）/自我否定（discard）”扩展。

---

### 2.7 `active_response/pipeline.py`
**功能**：主编排器，执行端到端主动响应决策。

**核心类**：
- `ActiveResponsePipeline`

**核心方法**：
- `run(utterances: list[Utterance]) -> list[DecisionEvent]`

**流程**：
1. 按 `start_ms` 排序输入语句。  
2. 拉取上下文并调用 `intent_engine.score`。  
3. 低分输出 `no_need`。  
4. 高分创建 pending（`end_ms + wait_ms`）。  
5. 若下一句在计划播报前开始，输出 `interrupted`；否则输出 `delivered`。  

**当前边界**：
- V1 仅处理首轮触发，不做完整多轮对话状态机。

---

### 2.8 `active_response/__init__.py`
**功能**：统一导出常用类，方便外部简洁导入。

**典型导出**：
- `V1Config, Utterance, IntentResult, PendingResponse, DecisionEvent, ContextBuffer`

---

### 2.9 `scripts/run_demo.py`
**功能**：提供可直接运行的最小演示。

**行为**：
- 构造几条样例 `Utterance`，调用 `ActiveResponsePipeline`，打印事件流（`no_need/interrupted/delivered`）。

---

### 2.10 `tests/test_pipeline.py`
**功能**：验证主流程三条关键路径。

**覆盖用例**：
- 低分 -> `no_need`
- 高分但被后续发言抢占 -> `interrupted`
- 高分且等待窗内无抢占 -> `delivered`

**测试方式**：
- 使用 `StubIntentEngine` 注入固定分数，保证测试稳定可复现。

---

## 3. 当前可扩展点（后续设计可直接接入）

1. 用真实模型替换 `RuleBasedIntentEngine`（不改 pipeline 接口）。  
2. 在 `ResponseManager` 上扩展多 pending 任务治理。  
3. 在 `pipeline` 增加 `merged/discarded` 的实际触发逻辑。  
4. 从“离线 utterance 列表”过渡到“流式输入事件循环”。
