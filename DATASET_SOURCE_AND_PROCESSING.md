# 数据集来源与处理说明

## 1. 数据集来源
本项目当前使用的外部语音数据来自 OpenSLR 的 AISHELL-5：

1. AISHELL-5 Dev  
   - 来源页：`https://www.openslr.org/159/`  
   - 下载地址：`https://www.openslr.org/resources/159/Dev.tar.gz`
2. AISHELL-5 Eval1  
   - 来源页：`https://www.openslr.org/159/`  
   - 下载地址：`https://www.openslr.org/resources/159/Eval1.tar.gz`


---

## 2. 本地存储位置

### 2.1 原始解压数据（当前使用）
- `G:\1.7b\data\raw\aishell5\Dev_extracted\Dev\...`
- `G:\1.7b\data\raw\aishell5\Eval1_extracted\Eval1\...`

---

## 3. 处理脚本与流程

### 3.1 采集与标准化处理
- 脚本：`scripts/collect_and_process_aishell5.py`
- 主要步骤：
1. 下载 Dev/Eval1（若本地不存在则下载）
2. 解压归档
3. 解析 `.TextGrid` 标注
4. 生成统一 JSONL 样本格式
5. 基于关键词规则生成弱标签 `label_should_respond`

### 3.2 训练/评测打包
- 脚本：`scripts/build_aishell5_active_response_pack.py`
- 作用：将弱标签数据打包为 `train/val/test` 三个 split，并输出统计摘要。

---

## 4. 统一数据字段定义
输出 JSONL 每行包含以下字段：
- `utterance_id`：语句唯一 ID
- `speaker_id`：说话人 ID
- `text`：语句文本
- `start_ms`：起始时间（毫秒）
- `end_ms`：结束时间（毫秒）
- `dataset`：来源数据集（Dev/Eval1）
- `session_id`：会话编号
- `source_file`：源 TextGrid 文件路径
- `label_should_respond`：弱标签（布尔）

---

## 5. 处理产物路径

### 5.1 collected 层（按 split 处理后）
- `data/collected/aishell5_dev_segments.jsonl`
- `data/collected/aishell5_dev_segments_weak.jsonl`
- `data/collected/aishell5_eval1_segments.jsonl`
- `data/collected/aishell5_eval1_segments_weak.jsonl`

### 5.2 pack 层（训练用打包）
- `data/pack/aishell5_active_response_weak/train.jsonl`
- `data/pack/aishell5_active_response_weak/val.jsonl`
- `data/pack/aishell5_active_response_weak/test.jsonl`
- `data/pack/aishell5_active_response_weak/summary.json`

---

## 6. 数据规模统计（当前版本）

### 6.1 弱标签明细
- Dev weak：`20,822` 条，正例 `487`，会话 `18`，TextGrid 文件 `108`
- Eval1 weak：`20,337` 条，正例 `215`，会话 `18`，TextGrid 文件 `108`

### 6.2 合并打包统计
- 总样本：`41,159`
- 正样本：`702`
- 正样本比例：`0.017056`
- 数据划分：
  - train：`32,927`
  - val：`4,115`
  - test：`4,117`

---

## 7. 使用注意事项
1. 当前标签为“弱标签”，适用于流程验证与初步训练，不等同于人工精标真值。  
2. 由于早期生成时路径尚在 `C:`，部分历史 JSONL 的 `source_file` 字段仍指向旧路径；不影响训练与评测核心字段（`text/start_ms/end_ms/label`）。  
3. 如用于正式论文/答辩结论，建议在半自动精标基础上补充人工复核后再重训。
