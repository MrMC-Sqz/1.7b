# 主动响应系统 V1 架构（可行版）

## 1. 目标边界
- 仅覆盖首轮主动响应：`是否响应 + 何时响应 + 首句响应`。
- 默认策略：不主动打断，按“当前句结束 + 等待窗口”触发。
- 输入前提：已完成语音分离，输入为多路分句 ASR（含时间戳）。

## 2. 核心数据结构
- `Utterance`: 一条语句（speaker_id, text, start_ms, end_ms）。
- `IntentResult`: 意图结果（score, should_respond, reason, draft_reply）。
- `PendingResponse`: 待播报任务（speaker_id, plan_time_ms, response, score, source_utt_id）。
- `DecisionEvent`: 决策结果（no_need / interrupted / delivered / merged / discarded）。

## 3. 模块拆分
1. `domain`（数据模型）
   - 定义上述 dataclass 与基础校验。
2. `context_buffer`（上下文管理）
   - 维护全局时间线与分说话人窗口。
   - 提供“最近 N 秒上下文”给意图模型。
3. `intent_engine`（意图评分）
   - 接口化：`score(context, current_utt) -> IntentResult`。
   - V1 提供可替换实现：`RuleBasedIntentEngine`（后续可接 Qwen）。
4. `timing_policy`（时机决策）
   - 规则：`plan_time = end_ms + wait_ms`。
   - 若 `next_start_ms < plan_time` 则 `interrupted`。
5. `response_manager`（挂起任务管理）
   - 管理 pending 队列，支持 keep/merge/discard。
6. `pipeline`（编排）
   - 串联缓冲、打分、挂起、触发与输出事件。

## 4. 处理流程
1) 接收 `Utterance` 并写入 `context_buffer`。  
2) 调用 `intent_engine` 得到 `score` 与 `draft_reply`。  
3) 低于阈值：输出 `no_need`。  
4) 高于阈值：创建 `PendingResponse`，计划播报时刻 `end_ms + wait_ms`。  
5) 到计划时刻前若检测新语句开始：输出 `interrupted`。  
6) 否则输出 `delivered`。  
7) 若检测到同一说话人补充约束，可执行 `merge`；若用户自我否定可 `discard`。

## 5. 配置项（V1 必需）
- `urgency_threshold`（默认 0.7）
- `wait_ms`（默认 800）
- `context_window_ms`（默认 10000）
- `max_pending_per_speaker`（默认 1）

## 6. 可验证成功标准
- 可在离线“带时间戳 utterance 列表”上完整跑通事件流。
- 至少覆盖 4 种事件：`no_need/interrupted/delivered/merged|discarded`。
- 模块接口稳定，可替换 `intent_engine` 而不改 `pipeline`。

## 7. 非目标（V1 不做）
- 真正并发 TTS 播放器与音频设备控制。
- 跨 Session 长期记忆。
- Barge-in 主动抢话。
