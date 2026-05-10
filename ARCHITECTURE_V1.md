# 主动响应系统 V1 架构说明

## 1. 项目目标
本项目用于车载语音场景下的“首轮主动响应”决策，核心回答三个问题：
1. 要不要主动响应（是否触发）
2. 什么时候响应（时机控制）
3. 第一条响应说什么（草稿回复）

当前版本以离线/准流式 JSONL 输入为主，便于实验与迭代评测。

## 2. 总体架构
系统采用分层解耦设计，`pipeline` 负责编排，其余模块各司其职：

- 输入层：ASR 片段（`Utterance`）
- 上下文层：`ContextBuffer`
- 意图打分层：`IntentEngine`（Rule / Qwen / ScoreHead）
- 时机策略层：`TimingPolicy`
- 挂起任务层：`ResponseManager`
- 输出层：`DecisionEvent`（`no_need / interrupted / delivered / merged / discarded`）

## 3. 核心数据结构
定义文件：[domain.py](/G:/1.7b/active_response/domain.py)

- `Utterance`：一条语音转写片段（说话人、文本、起止时间）
- `IntentResult`：意图模型输出（分数、是否响应、原因、草稿回复）
- `PendingResponse`：待播报任务（计划播报时间、来源语句、分数）
- `DecisionEvent`：最终事件流记录（用于评测与回放）

## 4. 模块职责
### 4.1 编排层
- [pipeline.py](/G:/1.7b/active_response/pipeline.py)
- 职责：串联“上下文 -> 打分 -> 挂起 -> 中断/投递”完整流程。

### 4.2 配置层
- [config.py](/G:/1.7b/active_response/config.py)
- 职责：统一管理阈值、等待窗口、模型开关、推理预算等参数。

### 4.3 意图引擎层
- [intent_engine.py](/G:/1.7b/active_response/intent_engine.py)
- 组件：
  - `RuleBasedIntentEngine`：高精度保守基线
  - `QwenIntentEngine`：真实大模型推理（`Qwen/Qwen3-1.7B`）
  - `ScoreHeadIntentEngine`：轻量判别头（可微调）

### 4.4 上下文层
- [context_buffer.py](/G:/1.7b/active_response/context_buffer.py)
- 职责：维护时间窗内上下文，支持按全局/说话人检索近邻语句。

### 4.5 时机策略层
- [timing_policy.py](/G:/1.7b/active_response/timing_policy.py)
- 职责：根据 `wait_ms` 计算计划播报时间，并判定是否被下一条语句打断。

### 4.6 挂起任务层
- [response_manager.py](/G:/1.7b/active_response/response_manager.py)
- 职责：管理每个说话人的 pending 队列，支持溢出丢弃、合并、取消。

## 5. 处理流程（单条语句）
1. 输入 `Utterance`
2. 取最近上下文窗口
3. 调用意图引擎得到 `IntentResult`
4. 若不满足阈值：输出 `no_need`
5. 若满足阈值：创建 `PendingResponse`
6. 若下一条语句提前到来：输出 `interrupted`
7. 若等待窗口到期：输出 `delivered`
8. 若检测到补充约束/取消语义：输出 `merged` 或 `discarded`

## 6. 数据与训练架构
### 6.1 数据管线
- 采集与处理：[collect_and_process_aishell5.py](/G:/1.7b/scripts/collect_and_process_aishell5.py)
- 切分打包：[build_aishell5_active_response_pack.py](/G:/1.7b/scripts/build_aishell5_active_response_pack.py)
- 半自动精标候选：[build_semiauto_annotation_pool.py](/G:/1.7b/scripts/build_semiauto_annotation_pool.py)
- 标注回流合并：[merge_review_labels.py](/G:/1.7b/scripts/merge_review_labels.py)

### 6.2 训练与评测
- 训练：[train_score_head.py](/G:/1.7b/scripts/train_score_head.py)
- 评测：[evaluate_offline.py](/G:/1.7b/scripts/evaluate_offline.py)

## 7. 快速使用（给新同学）
1. 环境检查：
```bash
python -m scripts.check_gpu
```
2. 基线评测：
```bash
python -m scripts.evaluate_offline --input data/sample_eval.jsonl
```
3. 跑半自动精标候选：
```bash
python -m scripts.build_semiauto_annotation_pool --input data/pack/aishell5_active_response_weak/train.jsonl --output-dir data/annotate_pool/stage1_rule_train --top-k 4000
```
4. 回流并训练 score-head：
```bash
python -m scripts.merge_review_labels --base data/pack/aishell5_active_response_weak/train.jsonl --review data/annotate_review/review_top_1200_autolabeled_guarded.jsonl --output data/annotate_review/train_merged_round1_guarded.jsonl
python -m scripts.train_score_head --train-jsonl data/annotate_review/train_merged_round1_guarded.jsonl --output-dir out/score_head_round3_guarded_bce_shuffle --epochs 1
```

## 8. 当前默认建议
- 线上默认：优先 Rule 引擎（稳健）
- 实验分支：ScoreHead 持续优化
- Qwen：用于高质量重判和标注辅助，不建议在 4GB 显存设备长时间并行混跑
