# BidPilot Handoff for CC

> 目标：接手当前 DocPilot / BidPilot 项目，继续推进“可落地的 VPS 控制试用”到“真正可商业化”的收口工作。

## 一句话结论

当前项目已经不是纯 MVP：核心 BidPilot 流程、鉴权、组织/团队、邮件、Turnstile、LangGraph 工作流、助手壳子、VPS 部署链路都已经有了。
但它**还不是完整的企业级正式商用版**，更准确地说是：

- 可以做内部演示
- 可以做受控 VPS 试用
- 还不适合直接当成开放式自助付费商业版发布

assistant 对话助手也已经有 v1，可用，但还没到“成熟企业级 AI 代理”的程度。

## 当前已完成的关键点

- BidPilot 主业务链路已落地：项目、文档、解析、证据、草稿、审阅、导出、执行运行。
- 后端有 `LangGraph` 工作流，且业务真值放在 PostgreSQL，不放在 prompt 里。
- 对话助手已有独立的 harness 风格接口和 SSE 事件。
- 助手已支持：
  - 发送消息
  - 意图识别
  - 缺参追问
  - 确认型操作
  - 工具调用展示
  - 执行结果卡片
  - 会话历史
  - 会话标题自动生成
- 鉴权、注册、登录、重置密码、Turnstile 校验都已接上。
- VPS 部署链路已跑通并上线过。

## 现在还没完全收口的地方

### 产品和 AI

- assistant 工具覆盖还不够全。
- assistant 的多轮上下文、状态流转、提示词边界还要继续收紧。
- assistant 和真实工作流进度还没完全打通。
- 目前更像“可用的 v1”，不是最终版企业 AI 代理。

### 商业化

- 没有完整的、持久化的 AI 用量账本。
- 免费试用额度 / 配额控制还不够企业级。
- Stripe / billing 还只是骨架级，不是正式商用级。
- 邮件投递、回退、告警、支持流程还需要继续补。

### 运维

- 还要继续做 release rehearsal、备份恢复演练、生产 smoke、监控告警。
- 还没到“未知用户直接可稳定自助注册付费”的程度。

## 服务器与部署现状

- VPS：`root@38.14.254.50`
- 系统：Debian 12
- 反代/证书：1Panel + OpenResty
- 1Panel 管理页：`http://38.14.254.50:10086/ztpanel`

### 线上域名

- Web：`https://bidpilot.rglens.com`
- API：`https://bidpilot-api.rglens.com`

### 端口与容器

只允许对外暴露 Web / API 反代入口，数据服务都只走内网或 `127.0.0.1`：

- Web：`127.0.0.1:3100`
- API：`127.0.0.1:3101`
- PostgreSQL：`127.0.0.1:5433`
- Redis：`127.0.0.1:6379`
- MinIO：`127.0.0.1:9000` / `127.0.0.1:9001`

补充：服务器上没有单独启用 UFW / firewalld，主要依赖云侧安全组 + 本地 loopback 绑定 + OpenResty 反代。

## 服务器目录结构

统一按 `/app/<project>` 方式部署。

BidPilot 当前结构：

- `/app/bidpilot/repo`：GitHub 仓库 checkout
- `/app/bidpilot/.env`：生产环境变量，不进仓库
- `/app/bidpilot/docker-compose.yml`：生产 compose
- `/app/bidpilot/deploy.sh`：统一更新入口

## 更新 / 发布流程

### 标准更新方式

直接执行：

```bash
cd /app/bidpilot
./deploy.sh
```

`deploy.sh` 的逻辑是：

1. `cd /app/bidpilot/repo`
2. `git pull --ff-only origin master`
3. `cd /app/bidpilot`
4. `docker compose up -d --build`

### 如果 repo 有本地脏改动

先 stash，再更新；不要硬重置：

```bash
cd /app/bidpilot/repo
git stash push -u -m "pre-deploy backup"
git pull --ff-only origin master
```

### 验证命令

部署后建议检查：

```bash
cd /app/bidpilot
docker compose ps
curl -I http://127.0.0.1:3100
curl -s https://bidpilot-api.rglens.com/health
```

## 生产环境变量

以下是需要保留在 VPS `.env` 或受管 secrets 里的变量名，不要把值写进仓库：

- `DOCPILOT_DATABASE_URL`
- `DOCPILOT_REDIS_URL`
- `DOCPILOT_MINIO_ENDPOINT`
- `DOCPILOT_MINIO_ACCESS_KEY`
- `DOCPILOT_MINIO_SECRET_KEY`
- `DOCPILOT_JWT_SECRET`
- `DOCPILOT_SECRETS_KEY`
- `DOCPILOT_APP_URL`
- `DOCPILOT_API_URL`
- `DOCPILOT_CORS_ORIGINS`
- `DOCPILOT_AUTH_REQUIRED=true`
- `DOCPILOT_LANGGRAPH_CHECKPOINTER=postgres`
- `DOCPILOT_SMTP_HOST`
- `DOCPILOT_SMTP_USER`
- `DOCPILOT_SMTP_FROM`
- `DOCPILOT_PROVIDER_DOMESTIC_API_KEY`
- `DOCPILOT_TURNSTILE_SECRET_KEY`
- `VITE_API_URL`
- `VITE_TURNSTILE_SITE_KEY`

## 当前部署状态

- 最近一次本地变更已成功推送到 GitHub。
- VPS 上已成功拉取并重建。
- 线上 web / api 健康检查通过。
- 构建缓存已清理过一次，磁盘压力已经缓解。

## 现在最该继续做的事情

### 第一优先级

1. 继续收紧 assistant 的多轮上下文和工具边界。
2. 把 assistant 的“状态条 / 工具调用 / 执行结果 / 历史会话”做得更像真正可用的企业助手。
3. 把工作流进度更完整地回流到 UI。

### 第二优先级

1. 做 durable AI usage ledger。
2. 做试用额度 / 配额 / rate limit 的后端强制执行。
3. 把 billing / subscription / entitlement 真正生产化。

### 第三优先级

1. 补齐 release rehearsal、备份恢复、告警和支持流程。
2. 完善邮件可达性和生产模板。
3. 做更严格的项目 / 组织权限审计。

## 需要 cc 先读的文档

- `docs/product/commercial-launch-gap-analysis.md`
- `docs/product/pilot-commercial-readiness.md`
- `docs/product/vps-to-commercial-launch-gap-list.md`
- `docs/ops/vps-pilot-deployment.md`
- `docs/ops/deployment-and-runbook.md`
- `docs/ops/release-checklist.md`
- `docs/ops/release-rehearsal-runbook.md`

## 重要提醒

- 不要把任何 API key、密码、Token、私钥写进仓库或交接文档。
- 不要随便重置 git 状态，不要回滚你没确认的用户改动。
- 当前仓库有一些预先存在的脏文件/缓存目录，接手时不要把它们当成这次改动的一部分去乱清。
- 商业化发布前，先确认试用额度、计费、恢复演练、邮件和告警都过一遍。

