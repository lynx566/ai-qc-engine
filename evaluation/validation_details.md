# DSUR Validation Details

评估日期：2026-10-15（Asia/Shanghai）。本公开详情版基于既有内部报告整理；评估过程仅离线读取既有运行产物，未调用 LLM 或重新运行 Flow。

精简结果见 [Validation Summary](validation_summary.md)。

## Sample-use disclosure

7 条 GT 在模型评估前预先冻结；未基于该样本调整 Prompt 或进行内容定向模型调优。正式重复运行前，该样本曾参与通用 consolidation 工程鲁棒性问题的排查与修复。因此本文的 held-out 仅指未参与 Prompt/内容定向调优，不表示该样本从未参与系统工程开发，也不作为严格 untouched benchmark。

版本核查确认 `f6ad354b7537f4fdfa62d0b4b9b03822ff5a4961` 包含 unclosed JSON-fence parser 处理。对于 singleton，需要区分三个行为：

- 输入 finding 数小于2：不调用 provider，自动 no-op；该版本已包含此行为。
- 未进入任何合并组的 finding：由 reconciliation 原样保留；R2有1条、R3有3条，不能据此推断模型返回单元素 group 也会被接受。
- provider 返回仅含一个 conclusion alias 的 consolidation group：该版本 response_validation.py 仍要求至少两个不同 alias，execution 测试亦把单 alias group 视为 validation failure。

因此，不能把“singleton-group acceptance 已修复”写成这份报告已核实的版本事实。上述两个保留/no-op 行为确实位于报告提交的代码树中；提交标题只描述本次 fence parser 改动，不是提交完整功能清单。本地 reflog 显示该提交通过 fast-forward pull 进入当前 checkout，没有本地 amend 记录；无法据此还原其他 checkout 的更早编辑历史。

可核对源码：[response validation](../backend/plugins/clinical_trial_doc/evidence_comparison/clinical_safety/aggregate_evidence/comparison_finding_consolidation/response_validation.py)、[finalization](../backend/plugins/clinical_trial_doc/evidence_comparison/clinical_safety/aggregate_evidence/finalization.py)、[reconciliation](../backend/plugins/clinical_trial_doc/evidence_comparison/clinical_safety/aggregate_evidence/comparison_finding_consolidation/reconciliation.py)、[execution tests](../backend/tests/test_comparison_finding_consolidation_execution_core.py)。这些相对链接展示当前 checkout 的代码；报告版本以完整提交号为准。

## Evaluation scope

评估对象为 **one held-out DSUR、7 条运行前冻结的 in-scope GT、3 次同版本成功重复运行**。三次运行是同一文档的重复试验，不是三个独立验证样本。GT 按核心错误命题判定，每条 GT 每次运行至多计一次；`Partial` 不计入严格 GT recall 的分子。原先设计的“研究人群错误”处于当前 comparison evidence 范围之外，不属于这 7 条 GT，也不计 missed。

### Run identity and provenance

| 简称 | Run ID（目录名） | Flow 完成时间（UTC） | Git provenance |
|---|---|---|---|
| R1 | `20261014_164211_859478Z` | 2026-10-14 16:51:17 | `f6ad354`, clean before_run |
| R2 | `20261014_171451_348187Z` | 2026-10-14 17:30:34 | `f6ad354`, clean before_run |
| R3 | `20261014_173939_493676Z` | 2026-10-14 17:49:54 | `f6ad354`, clean before_run |

完整 flow_run_id 为 `document_consistency_qc_` 加上对应目录名。`git_commit`、`git_dirty=false`、`git_dirty_checked_at=before_run` 均来自各自 evidence_comparison/run_summary.json；短提交号在本地唯一解析为 **`f6ad354b7537f4fdfa62d0b4b9b03822ff5a4961`**（`fix(finding-consolidation): handle unclosed JSON fences`），与核查时 HEAD 一致。该提交时间为 2026-10-15 00:07:38 +0800，即 2026-10-14 16:07:38 UTC，早于三次运行。

核查结果：**根据已持久化 provenance，可确认三次作为同版本 repeated trials 合并评估**，未发现需要排除的 run。依据如下：

- 三份 flow_run_summary.json 的输入文件名均为 `艾美妥珠单抗 研发期间安全性更新报告#2_错误模拟.docx`，文件哈希均为 `sha256:c1a86546b97287bd6bdf07e25f6cb1d11bb2da56a02db52d33609fdaa1f9a3f5`。
- 三份 aggregate_comparison_evidence.json 去掉运行生成的 `doc_id`、`aggregate_evidence_source_bundle_id` 后完全一致，包括 scope、句子标识、原文及其他字段；原始文件哈希差异来自这些标识。
- 三份 comparison_finding_assessment_jobs.json 字节一致（SHA-256 `bac840b07554f8d6ebf5ddadc3aea2315e73b6986b1aa38df2ed81b7dbaa091d`），均计划 20 个 job；20 个对应 assessment/prompt.txt 均逐字一致。
- 所有三次 evidence_comparison 已记录 invocation 的 provider/model 均为 `bailian_qwen` / `qwen3.7-plus-2026-05-26`，profile 均为 `qwen3_7_plus_2026_05_26`。
- assessment prompt 版本为 scope_local `0.3.3`、focus_comparison `0.3.2`；verification 为 scope_local `0.2.2`、focus_comparison `0.2.1`；consolidation 为 focus_comparison `0.1.0`，三次一致。三次共有的 17 个 verification prompt 的 system 部分逐字一致，consolidation system 部分亦一致。verification 和 consolidation 的 user 部分随上游 findings 变化，不能要求这些中间产物逐字相同。
- `llm_execution` 四项配置完全一致：assessment、assessment_second_pass、verification、consolidation 对应 `clinical_trial_doc_ec_assessment`、`clinical_trial_doc_ec_assessment_second_pass`、`clinical_trial_doc_ec_verification`、`clinical_trial_doc_ec_consolidation`；seed 均为 `1234`，response_format 均为 null，仅 second_pass 的 thinking=true，其余为 null。固定 seed 在本样本中没有带来逐字可复现结果。
- 三份 flow 状态均 success；run_summary.finalization 与 final_findings.json 均为 completed、fallback_comparison_modes=[]。

这项确认依赖运行时记录的提交号及 clean 标记，而非对历史进程内存或供应商后端版本的独立重建；当前供应商内部实现不可由这些本地产物验证。

### Public artifact availability

公开版保留完整评价、映射和附加发现分类，但不附带原始文档、LLM 请求/响应或 runtime 目录。本文中的 run IDs、finding IDs、句子 aliases 和文件名用于说明本次离线核查的追溯依据；公开读者不能仅凭本文独立重建运行。内部原始报告与运行产物保持原样。

核查读取了每次运行的 flow_run_summary.json，以及 evidence_comparison 下的 run_summary.json、findings.json、final_findings.json、aggregate_comparison_evidence.json、comparison_finding_assessment_jobs.json 和 consolidation persistence。

## Ground-truth results

下表中的 ID 均为 **对应 run 内 final finding ID**，不是全局 ID。`L` 表示 scope_local，`F` 表示 focus_comparison；括号中的 local/support 不单独代表完整 Detected。允许一个 final finding 涵盖两个不同 GT，但对每条 GT 分别按核心命题判定，不增加分母或重复计数。

| GT | Issue | Run 1 | Run 2 | Run 3 | Detection frequency |
|---|---|---|---|---|---|
| GT-01 | Ⅰ期研究状态：进行中 / 已完成 | Detected：L035(F) | Detected：L035(F) | Detected：L034(F) | 3/3 |
| GT-02 | 14/20 ADR 比例应为 70%，非 75% | Detected：L002(L)、L036(F) | Detected：L001(L)、L038(F) | Detected：L001(L)、L036(F) | 3/3 |
| GT-03 | Ⅰ期药物诱导肝损伤 2 / 1 例次不一致 | Detected：L003(L)、L038(F) | Detected：L003(L)、L039(F) | Detected：L003(L)、L038(F) | 3/3 |
| GT-04 | Ⅰ期达到 / 未达到 MTD 矛盾 | Detected：L034(F)；L005(L, support) | Detected：L036(F)；L004(L, support) | Detected：L035(F)；L004(L, support) | 3/3 |
| GT-05 | 14例、52例次 ADR 被写成 TEAE | Detected：L036(F)；L006(L, partial) | Partial：L005(L)；L038(F) 仅保留比例差异，不构成该 GT 的完整命中 | Detected：L025(F)；L005(L, partial) | 2/3；另 1/3 Partial |
| GT-06 | 联合治疗协同毒性肯定 / 否定矛盾 | Detected：L007(L)、L040(F) | Detected：L006(L)、L027(F) | Detected：L006(L)、L026(F) | 3/3 |
| GT-07 | 甲状腺功能异常纳入 RSI 与前文处置不一致 | Detected：L037(F) | Detected：L040(F) | Detected：L037(F) | 3/3 |

### Mapping rationale

- **GT-01**：三次对应 focus 结论均明确同一Ⅰ期研究“正在进行中”与“已完成”冲突。R1 引用 T0002/T0028；R2/R3 还包含 T0021。没有要求结论逐字复述冻结 GT，也未要求必须引用所有正确章节。
- **GT-02**：三次 local 结论均明确算式 14/20=70%，而非 75%；focus 分别补充跨位置证据。R1 L036 同时捕获事件名称不一致；R2 L038 虽只写 75%/70% 差异，但该 run 的 local 已完整识别计算错误。
- **GT-03**：local 均引用 T0022/T0024（R3 加 T0023），focus 将第4节 2例次与多处 1例次明确对照，核心矛盾稳定。但 **R3 L003 建议把累计数改为2例次，修正方向与冻结 GT 相反**。本任务按核心错误命题判定，故仍为 Detected；这不能作为正确修订建议的证据。
- **GT-04**：三次 focus 均直接比较 T0003“未达到”与 T0031“达到”，完整捕获核心矛盾。local 仅根据 T0031 的 DLT/MTD 临床逻辑提出质疑，属于同一 GT 周边支持，不能单凭该局部推断确认跨章节冲突或正确 MTD 结论。
- **GT-05**：R1 L036 明确指出同一 14例数据在 TEAE/ADR 名称上不一致，已识别核心分类冲突，因此为 Detected；其 local L006 仅推测缺少限定词，为部分识别。R2 L005 只提出“TRAE 或≥3级 TEAE”等候选解释，没有明确识别应为 ADR，故为 Partial。R3 L025 明确写出 ADR 被误表述为 TEAE，为 Detected。仅证据引用 T0042 或 source_finding_ids 含有正确上游 finding，不足以替代 final conclusion 的核心命题。
- **GT-06**：三次 focus 均把 T0055 的肯定表述与其他位置的否定结论对照，捕获协同毒性结论翻转；local 均提出疑漏“未”。R2 local L006 标为 need_review，而 focus L027 标为 fail；不影响本 run 的完整 GT 检出。
- **GT-07**：三次 focus 均明确甲状腺功能异常在结论新增至 RSI，而前文仅纳入肺炎/肝损伤或暂不纳入其他事件；引用均包括 T0086 及前文处置依据。R2 local L012 质疑监测计划遗漏甲状腺异常，claim 不同，单列 additional overlap，不算第二次 GT 命中。

### GT-05 consolidation trace

R2 job-final **L026** 明确写出：“前者术语‘治疗期间出现的不良事件（TEAE）’应为‘不良反应（ADR）’”，并同时识别 75% 应为 70%。它与只识别比例不一致的 **L016** 被合并成 final **L038**，`source_finding_ids=[L016,L026]`；但统一结论只剩“75.0%”与“70.0%”不一致，**ADR/TEAE 核心分类命题在 final 文本中丢失**。

可在 R2 `validated_response.json` 第4组（C004/C015）及 `alias_mapping.json` 追溯。因此不能用合并前 L026 把 R2 product-final recall 补成 7/7。

对照：R1 将比例及事件名称问题合并为 L036，保留两类不一致；R3 比例形成 L036，而 ADR/TEAE 问题以未合并的 L025 保留。**同一核心问题的合并结构会变化，而且至少一次影响语义保留。**

## Run-level metrics

GT recall = Detected / 7，不给 Partial 任意半分。scope_local / focus_comparison 数量均以 product-final 为准。

| Metric | Run 1 | Run 2 | Run 3 | Summary |
|---|---|---|---|---|
| Final finding count | 16 | 19 | 20 | range 16–20；mean 18.33 |
| fail count | 15 | 14 | 17 | range 14–17；mean 15.33 |
| need_review count | 1 | 5 | 3 | range 1–5；mean 3.00 |
| GT Detected / Partial / Missed | 7 / 0 / 0 | 6 / 1 / 0 | 7 / 0 / 0 | 6/7 条 GT 在全部三次均 Detected |
| Strict GT recall | 7/7 = 100% | 6/7 = 85.71% | 7/7 = 100% | 每个 run 独立对固定7条计数 |
| finalization_status | completed | completed | completed | 完成频率 3/3 |
| fallback modes | [] | [] | [] | fallback 频率 0/3 |
| Focus consolidation group count | 7 | 6 | 5 | 仅多 finding 合并组，不含未合并 singleton |
| scope_local final count | 9 | 12 | 12 | range 9–12 |
| focus_comparison final count | 7 | 7 | 8 | range 7–8 |
| Job-final finding count（合并前） | 31 | 34 | 33 | 与 findings.json 实际计数一致 |
| Focus consolidation input count | 22 | 22 | 21 | 与合并前 focus 实际计数一致 |
| Focus 未合并 singleton | 0 | 1 | 3 | R2：L027；R3：L015、L025、L026 |
| Consolidation execution / success / failed | 1 / 1 / 0 | 1 / 1 / 0 | 1 / 1 / 0 | 成功频率 3/3 |
| Consolidation alias QC mismatch groups | 3 | 4 | 4 | 均仅顺序差异，见下文 |
| 未映射至 GT 的 final finding 数 | 5 | 8 | 8 | 全部在下节逐项列出；不是假阳性数 |

## Finding stability

**GT 检出稳定性。** GT-01/02/03/04/06/07 的核心矛盾在三次均被 final findings 明确识别；GT-05 只有 2/3 完整检出。不能把“没有 Missed”写成“7条均稳定命中”，因为 R2 存在 Partial。

**Wording、evidence 与 structure。** 波动最大的为 GT-05：合并双命题、合并后丢失分类命题、分开保留三种结构均出现。GT-03 的证据边界与修正方向也值得关注，R3 local 对正确数值的方向判断错误，而 focus 仍保留 1/2 的矛盾。GT-07 的 focus source_finding_ids 数为 6/7/7、证据句数为 9/11/10，核心处置矛盾稳定，但支持证据组合有变化。GT-01 证据由2句增至3句；GT-04 focus 的两句直接矛盾最稳定；GT-06 核心稳定，但 local label 及是否合并不同。

**Cross-mode overlap。** GT-02、GT-03、GT-06 均在三次同时有 local 与 focus 捕获。GT-04 三次都有 local DLT/MTD 逻辑质疑和 focus 直接跨位置矛盾，但 claim boundary 不同。GT-05 三次都有 local“TEAE重复/缺限定词”提示；focus 对分类错误的明确表达只保留于 R1/R3。GT-01、GT-07 的完整识别主要由 focus 提供。以上仅用于 GT 映射，不意味着 product-final 应跨模式进一步合并，也不把所有重叠判为 duplicate。

**Finding-count variability。** 数量变化可从产物精确分解：R1 是 9 local +（7合并组 + 0 singleton）=16；R2 是 12 local +（6合并组 + 1 singleton）=19；R3 是 12 local +（5合并组 + 3 singleton）=20。R1→R2 增加3条全部来自 local 净增；R2→R3 增加1条来自 focus 净增。既有额外局部质疑的出现/消失，也有合并分组与 singleton 保留的变化，不能把总量上升解释为 GT recall 提高。其具体随机性来源不能仅凭三个产物归因到某一供应商机制。

**Label variability。** need_review 三次均出现，但数量为1/5/3，具体问题与标签也不稳定。肺炎/已知风险谱质疑（R1 L008、R2/R3 L007）的标签依次为 need_review/fail/fail；肺炎/糖皮质激素质疑（R1 L010、R2/R3 L008）为 fail/need_review/fail；GT-06 local 为 fail/need_review/fail。故“稳定出现 need_review”只适用于是否存在这一粗粒度指标，不适用于数量或问题级标签一致性；本样本显示明显运行间波动，但三次不足以估计其概率分布。

**Consolidation/finalization。** 三次调用均 parse_status=success、validation_status=success、status=success，finalization 均 completed，且没有 fallback。逐项核对 final 的 source_finding_ids：三次都恰好覆盖所有 job-final IDs，无遗漏或重复归属；final evidence aliases 均与所含 source findings 的有序并集一致。

三份 alias_qc.json 的 all_groups_match=false、mismatch_count=3/4/4。检查每组 missing/unexpected/duplicates 均为空，不一致均为 reported 与 expected 的**顺序**差异，不能写成证据句丢失或 consolidation 失败。然而 ID 和 evidence 保全并不保证 conclusion 语义保全：R2 GT-05 的命题丢失说明，“流程稳定完成”与“合并语义稳定”必须分开评价。

## Additional findings

下面逐项列出全部未计入7条 GT 的 final findings。分类是基于文档内部可解释证据的本次离线评阅，未完成临床专家 adjudication。`questionable / overcalling` 表示该 finding 的断言强于当前证据，不等于已证明其医学结论为假；凡涉及疾病机制、药物风险谱或用药适应证，最终仍 requires expert review。未计算 precision 或 F1。

| Run | Final ID | 原 label | 问题及内部证据评阅 | 分类 |
|---|---|---|---|---|
| R1 | L001 | fail | T0006 为 OOJ-VT8802-002，T0012 为 OOJ-VT8802-02，同一联合治疗研究编号不一致，原文直接可核实 | valid additional finding |
| R1 | L039 | fail | 同一编号不一致的跨位置版本，另引 T0039/T0058；与 L001 的证据范围不同 | valid additional finding |
| R1 | L008 | need_review | 从“已知PD-1/PD-L1风险谱一致”推测感染性肺炎应为免疫性肺炎；原文未提供足以排除感染性事件的机制证据 | uncertain / requires expert review |
| R1 | L010 | fail | T0069 将多种风险及处理措施概括列举，finding 将糖皮质激素直接限定为感染性肺炎的标准治疗并据此判错，断言超出句中明确对应关系 | questionable / overcalling；requires expert review |
| R1 | L011 | fail | 仅凭“药物诱导肝损伤”与“免疫介导毒性”用词认定机制互斥；文档未给出肝损伤机制，不能从内部证据确认互斥 | questionable / overcalling；requires expert review |
| R2 | L002 | fail | T0006/T0012 的 -002 / -02 编号差异直接成立 | valid additional finding |
| R2 | L037 | fail | 同一编号问题的 focus 版本，引用 T0006/T0039/T0021 | valid additional finding |
| R2 | L007 | fail | 与 R1 L008 同一肺炎/风险谱推断；升级为 fail 仍缺少文档内部足够依据 | questionable / overcalling；requires expert review |
| R2 | L008 | need_review | T0069 的肺炎/糖皮质激素联系可以提出医学复核问题，但多事件、多管理措施未逐项对应，不能内部确证 | plausible / need_review；requires expert review |
| R2 | L009 | need_review | T0079/T0080 已说明腹泻尚未作为严重不良反应纳入 RSI；是否严重尚待评估不是文本自相矛盾，finding 的分类追问不足以证明错误 | questionable / overcalling |
| R2 | L010 | need_review | T0079 为“肝功能相关实验室指标异常及其他免疫相关风险事件”，未明确把所有肝指标异常均归为免疫机制；机制判断无足够内部证据 | uncertain / requires expert review |
| R2 | L011 | need_review | T0086/T0088 的感染/肝损伤与免疫介导表述值得澄清，但不能整体确证为机制错误 | plausible / need_review；requires expert review |
| R2 | L012 | fail | 同围绕 T0086 的甲状腺异常展开，但 claim 是 T0088 后续计划遗漏；非穷尽性的“等”监测列举不证明遗漏，更非 GT-07 的前文/结论纳入冲突 | cross-mode overlap with a GT（GT-07）；遗漏断言有 overcalling 风险 |
| R3 | L002 | fail | T0006/T0012 编号差异直接成立 | valid additional finding |
| R3 | L015 | fail | 同一编号差异的 focus singleton，引用 T0006/T0039 | valid additional finding |
| R3 | L007 | fail | 继续根据典型风险谱推翻文内已记录的感染性肺炎；内部证据不能支持确定判错 | questionable / overcalling；requires expert review |
| R3 | L008 | fail | 同 R1 L010，T0069 未建立感染性肺炎与激素标准治疗的一对一关系，确定判错过强 | questionable / overcalling；requires expert review |
| R3 | L009 | need_review | 指责 T0079/T0080 未交代所有其他事件，未纳入同段 T0081 的后续分类评估说明，也未证明存在矛盾 | questionable / overcalling |
| R3 | L010 | need_review | T0075 的“重要已识别风险”与 T0084 的“无影响继续开发的新重大风险”不是同一命题；finding 附带条件提出疑问，但文本并无必然矛盾 | questionable / overcalling |
| R3 | L011 | need_review | 把“重要已识别风险”理解为必然已写入当前 RSI；同文 T0063 已明确“已升级、拟纳入”的更新过程，尚不足以认定不一致 | questionable / overcalling |
| R3 | L012 | fail | T0088 的“肺部感染……等免疫介导毒性”可能有术语/指代含混，值得澄清；但其是否为同一信号及实际机制不由内部证据确证 | plausible / need_review（本次评阅）；requires expert review |

未映射清单总数为 R1=5、R2=8、R3=8；上述分类不把同一问题跨模式出现的次数视为新增独立错误。编号差异是唯一三次稳定出现、可直接由原文确认的 additional issue，并且每次都有 local/focus 两条；这不自动证明两条应该合并。

反复出现的 questionable pattern 包括：以典型 PD-1/PD-L1 风险谱排除感染性肺炎、把概括性的激素管理举例读成每个事件的标准治疗、把“药物诱导”与“免疫介导”作为互斥机制、把选择性列举或 RSI 更新时序当成矛盾。前两类在三次均出现但 label 不稳定；后两类的具体对象和结论边界变化更大。因此 additional finding 不是稳定的假阳性清单，也不能简单全部当作真实额外错误。

## Limitations

- **Single-document evaluation**：只有一个 held-out DSUR，7条 GT 为预先冻结且受当前安全性 comparison scope 限定的集合，不能推断其他文档或 scope 外问题的表现。
- **Repeated runs are not independent samples**：三次共享输入、配置和代码，提供重复运行证据，不能当成三个独立验证样本或据此估计总体准确率。
- **Additional findings not fully adjudicated**：仅编号差异能直接从内部原文确认；其余多涉及机制、术语解释或风险处置边界，未完成专家裁决。不计算 precision、F1，不把模型 fail label 当作真实性结论。
- **Detection is not correction accuracy**：Detected 只表示核心错误命题被捕获，不要求逐字复述 GT，也不意味着修正方向、医学推理和证据边界全部正确。R3 GT-03 的错误修正方向是明确反例。
- **Completion is not semantic preservation**：三次成功且无 fallback，但 R2 consolidation 丢失 GT-05 的核心分类命题；source IDs、证据句保全不足以验证合并语义。
- **Limited provenance observability**：可核实本地持久化模型名、prompt/config 和运行前 git 标记，不能独立验证供应商内部更新，也不能把3次观察提升为执行成功率保证。
- **No generalization to overall clinical-document accuracy**：这些结果只支持 case-level GT recall 和 repeated-run stability evidence，不支持通用临床文档准确率、全面敏感性、产品 precision 或临床决策可靠性结论。

## Conclusion

在同一 held-out DSUR、同一记录代码版本和配置的三次运行中，6/7条冻结 GT 均稳定完整检出；GT-05 完整检出2/3，另一次仅 Partial，严格 run-level recall 为100%、85.71%、100%。三次 consolidation/finalization 均成功且无 fallback，但 R2 显示合并后核心分类命题丢失；不能宣称7条 GT 全部稳定命中，也不能把流程完成等同于语义无损。

Final findings 为16–20条、均值18.33；need_review 为1/5/3，反映额外局部质疑、标签以及合并结构的运行间变化。工程上，这一案例支持系统对六类核心内部矛盾具有重复检出能力，同时暴露 GT-05 合并语义保留、GT-03 修正方向和额外医学推断的复核需求。结论限于本案例；不支持总体临床文档准确率或 precision/F1 的推广性声明。
