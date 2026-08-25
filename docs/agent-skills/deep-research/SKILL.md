---
name: deep-research
description: Use for open-ended questions that need a bounded, source-grounded report with a plan, parallel retrieval, full-page reading, claim verification, uncertainty tracking, and citations. Do not use for a single factual lookup or a project-only evidence search.
license: MIT
---

# 通用深度调研

深度调研是一个可恢复的研究运行，不是连续调用联网搜索。先向用户说明范围、深度和禁止动作，再调用 `start_deep_research`；不要自行展开 `web_search` 循环。

## 运行契约

1. 把问题收敛成一个可验证的研究问题；缺少决定性边界时只问一个澄清问题。
2. 选择 `quick`、`standard` 或 `deep` 深度，并保留官方、原始或一手来源优先级。
3. 运行会并行生成互补检索计划，读取候选来源正文，去重并记录来源 ID。
4. 运行会把主张绑定到来源，区分已核验、冲突和待确认；没有证据不得补全事实。
5. 报告必须包含结论、证据、限制、风险、开放问题、建议和可点击来源；引用使用运行返回的来源 ID。

需要判断来源级别或检查报告结构时，读取 `references/source-quality.md` 或 `references/report-contract.json`；不要把这两份参考资料默认全部塞进上下文。`scripts/validate_report.py` 是确定性校验器，供 Worker/CI 验证报告结构，不是让模型自行发明校验结果。

## 收敛与交付

达到研究预算、来源不再增加、关键事实只能标记未知，或问题已足够回答时停止。后台运行可以等待；不要反复询问用户或重启同一个运行。只读研究不得创建项目、下载附件、导入资料或提交网站表单，除非用户另行确认并开始新的业务动作。
