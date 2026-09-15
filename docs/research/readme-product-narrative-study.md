# README 产品叙事研究

## 结论

BidPilot 的 README 采用产品 README 的信息顺序：

1. 产品名、类别和一句话结果；
2. 自有产品画面；
3. 在线体验、文档和源码入口；
4. 产品能力和完整工作路径；
5. 最短可执行上手路径；
6. 技术栈、架构和自托管细节；
7. 贡献、许可证和安全边界。

第一屏不放内部模块名、运行时解释、队列说明、旧实现迁移史或“本项目证明了什么”。这些内容只在 README 后半段作为查阅材料存在。

## 调研方法

- 使用官方 Tavily CLI 做了四轮公开检索，关键词覆盖 `open source product README`、`README product marketing hero screenshot feature gallery`、`SaaS README quick start` 和 BidPilot 已关注的开源项目；
- 使用 GitHub 官方仓库 API 和仓库 raw README 读取实际源码，而不是依据文章截图推断；
- 记录 2026-09-14 的源仓库 HEAD，便于后续复核；
- 只借鉴信息编排、视觉层级和入口设计，不复制第三方产品文案、品牌、截图、用户数字或源码。

## 参考项目

| 项目 | README 源码 | 观察到的有效结构 | BidPilot 采用点 |
| --- | --- | --- | --- |
| [AVIDS2/memorix](https://github.com/AVIDS2/memorix/tree/7071a49c178f3ea7aa3eb811fa802da4c436f28e) | [README.zh-CN.md](https://raw.githubusercontent.com/AVIDS2/memorix/7071a49c178f3ea7aa3eb811fa802da4c436f28e/README.zh-CN.md) | Hero、类别副标题、产品能力标签、快速入口、能力矩阵和技术细节分层 | 作为主母版，逐段沿用其中文 README 的首屏节奏、产品导航和能力矩阵组织方式 |
| [Twenty](https://github.com/twentyhq/twenty/tree/2f136f63385ca6f2678d59c8e3bc8590f6b411e8) | [README.md](https://raw.githubusercontent.com/twentyhq/twenty/2f136f63385ca6f2678d59c8e3bc8590f6b411e8/README.md) | 产品类别标题、官网/文档/路线图入口、首屏产品 banner、Why、Cloud / Self-hosting 分流、功能画面 | 采用“产品名 + 类别 + 画面 + 入口”的首屏骨架，以及云端/自托管分流 |
| [Formbricks](https://github.com/formbricks/formbricks/tree/d16cf35d970cd960662ea54521129358c3e7b760) | [README.md](https://raw.githubusercontent.com/formbricks/formbricks/d16cf35d970cd960662ea54521129358c3e7b760/README.md) | 一句话定位、使命句、产品画面、Features、Cloud / Self-hosting、开发入口 | 采用一句话产品定位、能力列表和体验/自托管入口分层 |
| [Langfuse](https://github.com/langfuse/langfuse/tree/791c7db5c2d63a1ce01535e5989cab44e3d60b45) | [README.md](https://raw.githubusercontent.com/langfuse/langfuse/791c7db5c2d63a1ce01535e5989cab44e3d60b45/README.md) | Hero 先展示产品、Cloud / Self-host / Demo / Docs 入口、功能画面、Quickstart、Security | 采用先看产品再看功能证据，最后给最短上手路径 |
| [Open SaaS](https://github.com/wasp-lang/open-saas/tree/cbd30162b05d798b3a3f955ab5781940b67bec89) | [README.md](https://raw.githubusercontent.com/wasp-lang/open-saas/cbd30162b05d798b3a3f955ab5781940b67bec89/README.md) | 产品演示入口、What's inside、Simple Instructions / Detailed Instructions、Docs 和反馈入口 | 采用“先能看到产品，再把上手拆成最短路径和完整文档” |
| [Cal.com](https://github.com/calcom/cal.com/tree/6bc45298226f96ff79e0c070c8b2ce39727e8477) | [README.md](https://raw.githubusercontent.com/calcom/cal.com/6bc45298226f96ff79e0c070c8b2ce39727e8477/README.md) | 产品画面、About、产品差异、Getting Started、Deployment 和 integrations 分区 | 采用产品画面、体验入口和部署细节分区；不复制其过长的集成清单 |
| [Hoppscotch](https://github.com/hoppscotch/hoppscotch/tree/d86e59f6e9574c69f01b300691b9f4396eeb38d2) | [README.md](https://raw.githubusercontent.com/hoppscotch/hoppscotch/d86e59f6e9574c69f01b300691b9f4396eeb38d2/README.md) | Features、Demo、Usage、Developing、CI、Changelog 的清晰分区 | 参考其 Demo / Usage / Developing 的分区命名，不采用其开发者工具的内容风格 |
| [awesome-readme](https://github.com/matiassingers/awesome-readme/tree/18195faec9697b21bb8086cfc8059c617b615b3d) | [README.md](https://raw.githubusercontent.com/matiassingers/awesome-readme/18195faec9697b21bb8086cfc8059c617b615b3d/README.md) | 收录“logo、短描述、动图/截图、快速安装、示例和文档”组合的项目 | 作为交叉校验，不作为产品文案来源 |

## 实际改版映射

| README 区域 | 本次处理 |
| --- | --- |
| Hero | 使用 `assets/readme-hero.svg` 的 BidPilot 适配版本；沿用 Memorix 的 README 视觉语言，替换产品名、业务词和交付链路，不使用第三方产品 Logo、截图和虚构数据 |
| 首屏文案 | 使用“招标资料 → 可交付响应方案”的结果表达；去掉“项目证明什么”“什么时候用”等工具说明 |
| 产品路径 | 用六步业务路径展示用户如何从建立项目走到导出文件 |
| 能力 | 用“工作 → 产品结果”表达，不用服务名堆砌功能 |
| Copilot | 保留用户能理解的工作方式和真实产品入口，不展开内部实现说明 |
| 技术内容 | 下沉到“开发者入口”和“运行时架构”，只保留已有代码、文档和部署事实 |
| 公开证明 | 保留公网体验、Archify 架构图、仓库文档和真实边界；不添加 fake customer、fake metrics 或未验收截图 |

## 版权与改写边界

本次没有复制参考项目的产品代码、Logo、用户数据或长段原文。`assets/readme-hero.svg` 和 `assets/tags/` 是从 `AVIDS2/memorix` README 图形资产派生的 BidPilot 适配素材；对应 Apache-2.0 归属见 [`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md)。BidPilot 的产品定义、能力、技术栈和限制均来自本仓库文档与代码。
