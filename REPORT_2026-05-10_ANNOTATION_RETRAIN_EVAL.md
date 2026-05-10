# 2026-05-10 标注回流 + 重训评测报告

## 1. 本轮完成范围
- 完成数据迁移与校验（`C:` -> `G:`）
- 完成半自动精标候选生成（Stage1/2/3）
- 完成标注回流流程（含策略对比）
- 完成 ScoreHead 重训与离线评测
- 形成可复现结论与产物清单

## 2. 数据迁移结果
- 原始数据目录：
  - `G:\1.7b\data\raw\aishell5\Dev_extracted`
  - `G:\1.7b\data\raw\aishell5\Eval1_extracted`
- 完整性统计：
  - `Dev_extracted`：228 文件
  - `Eval1_extracted`：230 文件
- 压缩包备份：
  - `C:\Users\46638\dataset_cache\aishell5_archives\Dev.tar.gz`
  - `C:\Users\46638\dataset_cache\aishell5_archives\Eval1.tar.gz`

## 3. 半自动精标与回流
### 3.1 候选池生成
- Stage1（规则全量筛）：`data/annotate_pool/stage1_rule_train/summary.json`
- Stage2（规则 + score-head 重排）：`data/annotate_pool/stage2_scorehead_train_top4k/summary.json`
- Stage3（Qwen 小样本深筛）：`data/annotate_pool/stage3_qwen_only_top1200_sample120/summary.json`

### 3.2 回流策略对比
- 激进策略（`ensemble`）：
  - 将 563 条原弱正样本改为负样本
  - 导致训练集正例塌陷，模型退化为全负预测
  - 判定：不可用于交付
- 保守策略（`no_downgrade_rule`）：
  - 规则：`新标签 = 原弱标签 OR rule_pred`
  - 回流结果：`changed_rows=0`
  - 产物：
    - `data/annotate_review/review_top_1200_autolabeled_guarded.jsonl`
    - `data/annotate_review/train_merged_round1_guarded.jsonl`

## 4. 训练链路修复
本轮发现并修复了两个关键问题：
1. 推理分数缩放错误  
   - 旧逻辑：`clamp(logit)`  
   - 新逻辑：`sigmoid(logit)`
2. 数据切分问题  
   - 旧逻辑：不打乱直接切分，易导致训练集无正样本  
   - 新逻辑：按 `seed` 打乱后切分

同时训练损失统一为 `BCEWithLogitsLoss`，并支持 `pos_weight` 自动平衡。

## 5. 重训配置与日志
- 模型输出：`out/score_head_round3_guarded_bce_shuffle/`
- 训练命令（核心）：
  - `python -m scripts.train_score_head --train-jsonl data/annotate_review/train_merged_round1_guarded.jsonl --output-dir out/score_head_round3_guarded_bce_shuffle --epochs 1 --batch-size 4 --eval-ratio 0.1 --seed 42`
- 关键日志（`out/train_score_head_round3.log`）：
  - `train_size=29635 eval_size=3292`
  - `train_pos=500 train_neg=29135 pos_weight=58.27`
  - `eval_f1=0.1045 eval_acc=0.7345`

## 6. 评测结果
## 6.1 弱标测试集（N=4117）
- Rule（threshold=0.7）：
  - precision=1.0000 recall=0.0588 f1=0.1111 accuracy=0.9845
  - 文件：`out/metrics_test_rule_before.json`
- ScoreHead（重训后）：
  - threshold=0.5：precision=0.0147 recall=0.6912 f1=0.0289 accuracy=0.2320
  - threshold=0.7：precision=0.0149 recall=0.6912 f1=0.0292 accuracy=0.2410
  - 文件：
    - `out/metrics_test_scorehead_after_round3_t05.json`
    - `out/metrics_test_scorehead_after_round3_t07.json`

结论：在当前弱标分布下，Rule 仍显著优于 ScoreHead（F1 更高且误报更低）。

## 6.2 真实 ASR 导出集（N=24）
- Rule（threshold=0.7）：
  - precision=0.9091 recall=0.7143 f1=0.8000 accuracy=0.7917
  - 文件：`out/metrics_asr_rule_before.json`
- ScoreHead（重训后）：
  - threshold=0.5：precision=0.6190 recall=0.9286 f1=0.7429 accuracy=0.6250
  - threshold=0.7：precision=0.5789 recall=0.7857 f1=0.6667 accuracy=0.5417
  - 文件：
    - `out/metrics_asr_scorehead_after_round3_t05.json`
    - `out/metrics_asr_scorehead_after_round3_t07.json`

结论：小样本真实集上 ScoreHead 可用，但本轮整体仍未超过 Rule 基线。

## 7. 交付结论与建议
- 本轮“回流 -> 重训 -> 评测 -> 报告”流程已闭环。
- 交付默认建议：
  - 线上默认采用 Rule 引擎
  - ScoreHead 保持实验分支持续迭代
- 下一轮建议：
  1. 人工精标真实正例（优先高分歧样本）
  2. 扩大真实 ASR 验证集规模
  3. 针对极端类别不平衡做阈值校准与分层采样训练
