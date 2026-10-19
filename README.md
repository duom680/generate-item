# Knowledge-Graph and Confusion-Prior Guided Distractor Generation

面向概念型选择题的干扰项生成方法：通过**混淆先验 → 局部知识图谱证据 → LLM 候选过生成 → 四维质量评分与 Top-3 筛选**，组织可复用的主流程代码。

本仓库是**原研究代码的精简公开实现**，保留核心方法与完整提示词，不包含数据集、知识图谱实体文件、模型权重、API 密钥、个人运行路径、实验记录、指标结果、消融与参数实验脚本。由于进行了模块重构、接口去耦与安全清理，公开版本不保证与原始实验代码逐行相同，也不应被用于暗示已复现论文所有实验结果。

## 工作流

```
                 q=(x,a)
                    │
  1. prepare        ▼
        题型 / 题干极性识别 ──► 混淆先验 Cq
                    │
        KG 实体链接 / K 跳邻域 / 知识路径 Gq,Pq
                    │
  2. generate       ▼
        结构化提示词 ──► LLM 过生成（默认 M=12）
                    │
  3. select         ▼
        语义接近 s_sim / 题干相关 s_q
        KG 一致 s_kg / 组内多样性 s_div
                    │
        基本约束 ─► 题内动态门控 ─► 去冗余 Top-3
```

## 代码目录

| 文件 | 作用 |
| --- | --- |
| `main.py` | 三阶段命令行入口 |
| `src/concept_distractors/graph.py` | 知识图谱导入、实体链接、邻域与路径提取 |
| `src/concept_distractors/prior.py` | 题型与混淆先验构建 |
| `src/concept_distractors/prompts.py` | **完整的约束系统提示词、结构化用户提示词** |
| `src/concept_distractors/generation.py` | API 环境变量读取、候选解析、去重与补生成 |
| `src/concept_distractors/ranking.py` | 四维评分、动态门槛、贪心冗余控制与 Top-3 |
| `tests/test_core.py` | 无真实数据、无外部 API 的代码单元测试 |

## 你需要自行提供的文件格式

**题库**为 JSON 数组，每条记录至少包含 `id`、`question`、`correct_answer`，也可提供 `chapter`、`question_type`、`answer_shape`、`seed_entities`。

**图谱**采用两个 UTF-8 CSV 文件：节点表至少含 `id,name`，关系表至少含 `source,relation,target`。支持部分常用同义列名。正式使用前请确保关系方向和语义准确。

以上仅为字段说明，不包含实际数据或示例题目。

## 使用（在仓库根目录执行）

```powershell
python main.py prepare --input data/questions.json --nodes data/nodes.csv --edges data/edges.csv --hop 2 --output outputs/prepared.json
```

在**你自己的本地终端**设置 API 凭据，不要将凭据写进脚本、README、`.env` 或上传至 GitHub：

```powershell
$secret = Read-Host "输入本地 API 凭据" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try { $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
# 仅当你的服务采用兼容接口时，在本地另行设置 OPENAI_BASE_URL
python main.py generate --input outputs/prepared.json --output outputs/candidates.json --model YOUR_MODEL_ID
python main.py select --input outputs/candidates.json --output outputs/selected.json --gate-percentile 20
```

> 候选生成会调用你自行配置的模型服务，并可能产生费用。模型和接口地址由使用者提供，仓库中不会记录真实凭据、接口地址或原始输出日志。

如需使用**已在本地**的语义向量模型，可为 `select` 增加 `--local-embedding-model "<本地模型文件夹>"`。不提供此参数时仅使用字符级相似性；为避免自动下载，仓库不指定预训练模型标识或提供模型文件。相关运行组件请根据你自己的环境自行配置，此处不列出依赖清单与版本锁定文件。

## 筛选说明

候选经过四维评分与形态一致性调整后，先执行等价性、形态及明显偏题风险检查；然后以**通过基本约束的候选项**计算题内分数百分位阈值（默认为第 20 百分位），通过门控后执行去冗余 Top-3。门控后不足三项时，只允许从已通过基本约束的候选项中回退选取；不足三项标为 `partial_need_regeneration`，不强行制造候选。

第 20 百分位是**题内质量分数的分位阈值**，而非“仅保留最高 20%”，也不是“四维各自通过 20%”。相关门控语义及公开版实现应与论文正式描述逐项核对。

