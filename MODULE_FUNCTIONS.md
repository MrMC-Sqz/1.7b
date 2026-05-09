# 主动响应项目模块说明（V1 扩展版）

## 架构总览
1. `active_response/domain.py`：领域对象定义（Utterance/IntentResult/PendingResponse/DecisionEvent）
2. `active_response/config.py`：运行参数（阈值、等待窗、Qwen 配置、多 pending 上限）
3. `active_response/context_buffer.py`：上下文缓存与时间窗查询
4. `active_response/intent_engine.py`：意图评分引擎（Qwen3-1.7B + 规则回退）
5. `active_response/response_manager.py`：多 pending 队列治理
6. `active_response/timing_policy.py`：时机规则函数
7. `active_response/pipeline.py`：离线与流式统一编排
8. `scripts/run_demo.py`：离线/流式演示
9. `tests/test_pipeline.py`：核心路径测试

---

## 1) `active_response/domain.py`
**功能**：统一数据结构，保障模块间接口稳定。  
**核心对象**：
- `Utterance`: 输入语句（说话人、文本、起止时间）
- `IntentResult`: 意图打分结果
- `PendingResponse`: 待播报任务
- `DecisionEvent`: 决策事件（`no_need/interrupted/delivered/merged/discarded`）

---

## 2) `active_response/config.py`
**功能**：集中配置系统行为。  
**关键参数**：
- `urgency_threshold`
- `wait_ms`
- `context_window_ms`
- `max_pending_per_speaker`
- `use_qwen_intent_engine`
- `intent_model_name`（默认 `Qwen/Qwen3-1.7B`）
- `intent_device_map`
- `intent_max_new_tokens`

---

## 3) `active_response/context_buffer.py`
**功能**：维护全局时间序列上下文。  
**接口**：
- `add_utterance(utt)`
- `recent_context(current_end_ms, window_ms)`
- `recent_by_speaker(speaker_id, current_end_ms, window_ms)`

---

## 4) `active_response/intent_engine.py`
**功能**：统一 `score(context, current_utt)` 接口，支持真实模型与回退。  
**组件**：
- `IntentEngine` / `BaseIntentEngine`
- `QwenIntentEngine`：主引擎，调用 `Qwen/Qwen3-1.7B`，输出 JSON（score/should_respond/reason/reply）
- `RuleBasedIntentEngine`：回退引擎（当推理环境不可用时接管）

**说明**：
- pipeline 不感知底层模型差异，只消费 `IntentResult`。

---

## 5) `active_response/response_manager.py`
**功能**：按说话人管理多 pending。  
**接口**：
- `add_pending(pending, max_pending_per_speaker)`：入队并按上限淘汰旧任务
- `discard_pending(speaker_id)`：丢弃该 speaker 最新任务
- `merge_latest_pending(speaker_id, supplement, new_plan_time_ms)`：合并补充约束
- `pop_due(current_time_ms)`：取出到期任务（用于 delivered）
- `get_latest_pending/all_pending`

---

## 6) `active_response/timing_policy.py`
**功能**：时机判定基础函数。  
**接口**：
- `plan_time(end_ms, wait_ms)`
- `is_interrupted(next_start_ms, planned_time_ms)`

---

## 7) `active_response/pipeline.py`
**功能**：主调度器，支持离线与流式。  
**核心接口**：
- `run(utterances)`：离线批处理
- `process_utterance(utterance, next_start_ms=None)`：流式逐条处理
- `finalize()`：刷出剩余到期任务

**触发逻辑**：
- 低分：`no_need`
- 高分且被后续语句抢占：`interrupted`
- 高分且等待窗通过：`delivered`
- 同说话人补充约束：`merged`
- 同说话人取消/自闭环：`discarded`
- 队列超限淘汰：`discarded(reason=pending_queue_overflow)`

---

## 8) `scripts/run_demo.py`
**功能**：运行离线与流式两个示例，打印事件流。  
**用途**：本地快速验收流程是否通畅。

---

## 9) `tests/test_pipeline.py`
**功能**：验证关键行为。  
**覆盖点**：
- `no_need`
- `interrupted`
- `delivered`
- `merged + discarded`
- 流式模式下到期任务刷出行为
