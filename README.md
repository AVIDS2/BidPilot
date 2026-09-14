# BidPilot

## 把招标资料，变成可以交付的响应方案

BidPilot 是为投标负责人、方案工程师和评审团队设计的 AI 投标响应工作台。

它把一次投标所需要的资料、要求、证据、响应章节、团队审核和最终文件，放进同一个项目里。你不需要在文件夹、聊天记录和表格之间来回寻找答案，也不需要把同一个项目背景重复讲给 AI。

<p align="center">
  <a href="https://bidpilot.rglens.com/">打开公网体验</a>
  ·
  <a href="docs/product/non-developer-demo-guide.md">15 分钟产品路径</a>
  ·
  <a href="docs/architecture/bidpilot-runtime.architecture.html">查看系统架构</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/AI%20投标响应-产品工作台-0f766e?style=for-the-badge" alt="AI bid response workspace">
  <img src="https://img.shields.io/badge/来源可追溯-每个结论都有依据-2563eb?style=for-the-badge" alt="source grounded">
  <img src="https://img.shields.io/badge/审核后交付-DOCX%20%2F%20PDF-7c3aed?style=for-the-badge" alt="approved export">
</p>

> 一份好的响应，不只是写得像。它还要说得清依据、经得起审核，最后真的能交付。

## 一次投标，完整走完

```mermaid
flowchart LR
    A[建立项目] --> B[放入招标与企业资料]
    B --> C[看清要求与缺口]
    C --> D[生成有来源的响应草稿]
    D --> E[团队审核与修改]
    E -->|退回重做| D
    E -->|批准| F[导出提交文件]
```

### 1. 建立项目

每个机会都有自己的工作区。项目负责保存资料范围、团队成员、响应结构、审核决定和交付状态。

### 2. 放入资料

上传招标文件、企业能力资料、历史案例和补充材料。资料会留在项目边界内，解析状态和处理进度清楚可见。

### 3. 看清要求

从长文档里整理出要求、评分点、合规规则、时间节点和待补信息。你看到的不只是摘要，还有来源位置和当前缺口。

### 4. 起草响应

Copilot 读取当前项目上下文，围绕章节和证据推进工作。没有来源支持的内容会被标记为缺口，而不是被写成确定事实。

### 5. 团队审核

负责人可以评论、退回、要求补充依据，再生成下一版。每一版都保留，谁改了什么、为什么改，都能回看。

### 6. 交付文件

只有批准后的内容才能进入交付。最终输出可以导出为 DOCX/PDF，和对应的版本、依据与审核决定保持关联。

## 你真正得到的产品能力

| 工作 | BidPilot 的产品结果 |
| --- | --- |
| 管理一次投标 | 一个清晰的项目工作区，资料、要求、响应和交付集中在一起 |
| 整理招标资料 | 招标文件、企业资料和案例材料按项目归档并持续处理 |
| 找到真正重要的要求 | 结构化要求清单、评分点、优先级和待补缺口 |
| 让内容有依据 | 要求、证据和响应章节之间保持来源关系 |
| 让 AI 参与工作 | Copilot 结合项目上下文推进查询、整理、起草和受控动作 |
| 让团队放心审核 | 章节版本、评论、退回、批准和审计记录完整保留 |
| 交付一份能用的文件 | 从批准版本生成 DOCX/PDF，而不是把聊天记录当成最终成果 |

## Copilot 是工作伙伴，不是另一个聊天框

你可以直接问：

> 查看这个项目的资料、需求和当前准备度，指出缺口并给出来源位置。

也可以继续说：

> 根据已经确认的资料，起草“技术响应方案”章节；如果依据不足，先告诉我缺什么。

Copilot 会在项目上下文里工作：

- 先理解当前项目、资料和任务状态，再决定下一步；
- 读取动作可以直接返回结果，写入、起草和有成本的动作会进入真实的审批流程；
- 长任务会在后台继续，页面刷新或浏览器断开不会抹掉项目进度；
- 子任务只是当前工作的执行步骤，不会污染用户的会话记录；
- 所有业务写入都经过权限、项目范围、审计和版本规则。

这不是“输入一个关键词，触发一段脚本”。你提出的是业务目标，Copilot 根据项目事实和可用能力推进工作。

## 项目记忆，让团队不用重复解释

BidPilot 把项目经验分成几个用户能理解的范围：

| 记忆范围 | 它帮助团队记住什么 |
| --- | --- |
| 当前工作上下文 | 现在在哪个项目、处理哪份资料、还有哪些待确认事项 |
| 工作记录 | 已经完成了什么、做过哪些修改、审核为什么退回 |
| 项目知识 | 已确认的事实、要求、风险、决定和术语 |
| 团队方法 | 团队模板、写作规范、审批规则和可复用流程 |

项目事实和证据不会因为一次聊天结束就消失，也不会因为模型“记得”某件事就自动变成正式结论。需要长期保留的知识，先提出，再经过确认。

## 产品界面围绕业务，而不是围绕内部服务

用户进入的是：

`项目` · `资料` · `要求` · `响应` · `评审` · `交付` · `项目知识`

内部的运行事件、队列、checkpoint 和 provider payload 只在需要恢复或排障时出现，不会成为普通投标用户的主导航。

## 运行时架构

详细架构图由官方 [Archify](https://github.com/tt-a1i/archify) JSON-IR 流程生成，并经过 `showcase` 校验与真实浏览器验收。

<p align="center">
  <a href="docs/architecture/bidpilot-runtime.architecture.html">
    <img src="docs/architecture/bidpilot-runtime.architecture.visual-check.1440x900.light.png" alt="BidPilot 运行时架构图" width="100%">
  </a>
</p>

README 展示的是经过验收的静态架构图；[下载并本地打开交互式 HTML](docs/architecture/bidpilot-runtime.architecture.html) · [查看源规格](docs/architecture/bidpilot-runtime.architecture.json) · [查看验收报告](docs/architecture/bidpilot-runtime.architecture.visual-check.json)

产品运行时分成几条清晰的责任边界：

| 产品部分 | 负责什么 |
| --- | --- |
| Web 工作台 | 展示项目业务、流式进度和审核结果 |
| FastAPI 控制面 | 负责身份、权限、项目范围、审批、审计和业务写入 |
| Pi Copilot | 负责交互式模型会话、原生工具调用和流式生命周期 |
| Celery Worker + LangGraph | 负责资料解析、检索、起草、验证、恢复和导出 |
| PostgreSQL + pgvector | 保存项目、要求、证据、版本、审核和运行事实 |
| Redis | 负责任务投递、outbox 和短期协调 |
| MinIO / S3 | 保存私有源文件和批准后的交付制品 |
| MiMo / OpenRouter | 通过 provider adapter 提供推理和向量能力 |

PostgreSQL 是业务事实的来源。Pi、LangGraph checkpoint、浏览器状态和模型输出都不是审批或交付的最终依据。

## 公开体验

打开 [BidPilot 公网演示](https://bidpilot.rglens.com/)，从一个项目开始。

公开演示使用 [`sample-data/bidpilot-demo`](sample-data/bidpilot-demo) 中的合成智慧社区资料，不代表真实采购方、供应商或客户。请不要上传真实投标文件、个人信息或生产密钥。

推荐体验顺序：

1. 创建一个项目；
2. 上传三份合成资料；
3. 查看要求、证据和缺口；
4. 起草一个响应章节；
5. 退回一次并带反馈重新起草；
6. 批准版本并导出 DOCX/PDF；
7. 回看版本、审核和项目知识。

完整的非开发者路径见 [产品演示指南](docs/product/non-developer-demo-guide.md)。

## 开发者入口

如果你需要研究实现细节，从 [文档地图](docs/README.md) 开始：

- [Harness 与 Pi Assistant 运行时](docs/architecture/assistant-harness-runtime.md)
- [执行与 LangGraph 工作流](docs/architecture/execution-and-workflow-architecture.md)
- [API 与事件合同](docs/architecture/api-and-event-contracts.md)
- [数据模型](docs/architecture/data-model.md)
- [本地环境基线](docs/development/local-environment-baseline.md)
- [部署与运行手册](docs/ops/deployment-and-runbook.md)
- [面试演示脚本](docs/product/interview-demo-script.md)

### 本地启动

本地前置条件和启动命令见 [本地环境基线](docs/development/local-environment-baseline.md)。UI/API 合同验证可以使用 SQLite；完整资料解析、向量索引和长流程需要 PostgreSQL、Redis 与 MinIO/S3。

### 技术栈

`React` · `TypeScript` · `Tailwind` · `shadcn/ui` · `FastAPI` · `Pydantic` · `SQLAlchemy` · `Celery` · `Redis` · `PostgreSQL` · `pgvector` · `MinIO/S3` · `Pi` · `LangGraph`

## 诚实边界

BidPilot 是面向个人项目和面试展示的 controlled pilot reference implementation。它已经覆盖一条真实的资料、证据、Agent、审核和导出链路，但不把演示环境包装成已经完成商业 GA 的 SaaS。

当前不声称已经完成：企业 SSO/SCIM 的商业化部署、水平扩展、长期真实用户质量验证、完整支付运营、实时协同编辑和通用自主编程 Agent。

## 安全

provider key、数据库 URL、对象存储密钥、JWT/Fernet secret 和邮件/支付密钥只应放在服务端环境或 secret store。浏览器不接触 provider key，不绕过 API 直接访问数据库、Worker、Pi 或对象存储。

安全边界与治理规则见[安全与治理文档](docs/security/security-and-governance.md)。发现安全问题不要开公开 Issue。

## License

BidPilot 自身代码按 [MIT License](https://github.com/AVIDS2/BidPilot/blob/master/LICENSE) 发布。第三方依赖、模板、字体和复用组件仍受其各自许可证约束。
