# DocPilot Development Workflow

## 核心规则

**Build in phase order.** 不要把roadmap当作可选想法的集合。

**Skills驱动开发。** 后端使用langgraph-skills，前端使用shadcn + taste-skills。

---

## 一、执行循环（每次Session）

参考：`docs/development/agent-execution-manual.md`

```
1. 识别当前Phase
2. 通过Preflight检查（docs/development/development-preflight-checklist.md）
3. 阅读Phase计划和相关文档
4. 选择下一个未实现的切片
5. 验证不确定的API、Schema、工具用法
6. 实现最小可行切片
7. 运行最佳可用验证
8. 更新文档（如果架构、运维、范围、契约有变更）
9. 确保仓库状态可被下一个session继续
```

---

## 二、Skills使用规范

### 2.1 后端开发：langgraph-skills

**必须使用的情况：**
- ✅ 实现或修改LangGraph图结构
- ✅ 添加或修改Agent节点
- ✅ 变更路由逻辑（Supervisor/Router/Orchestrator）
- ✅ 实现Human-in-the-loop审核
- ✅ 调试多Agent协调问题

**使用的Skills：**
- `langgraph-agent-patterns` - 多Agent协调模式
- `langgraph-docs` - LangGraph官方文档

**触发流程：**
```bash
# 1. 激活skill
<使用Skill工具调用 langgraph-agent-patterns>

# 2. 根据场景选择模式
- Supervisor: 复杂工作流，需要LLM智能路由
- Router: 简单分类，确定性规则
- Orchestrator-Worker: 并行执行，需要聚合结果
- Handoffs: 顺序工作流，逐步构建

# 3. 遵循skill中的最佳实践
- 状态设计（TypedDict + agent_history）
- Agent节点模板（错误处理 + 降级机制）
- 路由逻辑（LLM or 确定性）
- 检查点（PostgresSaver）
- 迭代控制（max_iterations）

# 4. 验证图结构
python scripts/validate_agent_graph.py services/worker/app/graph/builder.py:graph
```

**关键检查清单：**
- [ ] 使用了合适的Agent模式
- [ ] 状态有清晰的输入输出字段
- [ ] 有Agent历史追踪（agent_history）
- [ ] 有错误处理和降级机制
- [ ] 有迭代控制（max_iterations）
- [ ] 使用PostgresSaver检查点
- [ ] 关键节点支持HITL（interrupt_before）
- [ ] 通过图验证脚本

### 2.2 前端组件：shadcn

**必须使用的情况：**
- ✅ 添加新的UI组件
- ✅ 修改现有组件样式
- ✅ 集成第三方组件库
- ✅ 解决组件问题

**使用的Skills：**
- `shadcn` - 组件库管理

**触发流程：**
```bash
# 1. 激活skill
<使用Skill工具调用 shadcn>

# 2. 搜索和添加组件
npx shadcn@latest search <component>
npx shadcn@latest add <component>
npx shadcn@latest info <component>

# 3. 遵循组件规范
- 优先使用shadcn组件，不要自定义基础组件
- 扩展组件遵循标准模式
- 支持响应式和暗黑模式
```

**关键检查清单：**
- [ ] 优先使用shadcn组件
- [ ] 组件扩展遵循规范
- [ ] 有TypeScript类型定义
- [ ] 有单元测试
- [ ] 支持响应式
- [ ] 支持暗黑模式
- [ ] 符合无障碍标准

### 2.3 前端设计：taste-skills

**必须使用的情况：**
- ✅ 设计新页面
- ✅ 重大UI改版
- ✅ 提升视觉品质
- ✅ 优化用户体验

**使用的Skills：**
- `high-end-visual-design` - 高端视觉设计
- `design-taste-frontend` - 前端审美设计

**触发流程：**
```bash
# 1. 激活skill
<使用Skill工具调用 high-end-visual-design>

# 2. 遵循设计原则
- 视觉层次感（阴影、渐变、大小对比）
- 精致的细节（边框、圆角、图标）
- 舒适的间距（8px基准网格）
- 优雅的动画（平滑过渡、自然反馈）

# 3. 通过设计检查清单
```

**关键检查清单：**
- [ ] 有清晰的视觉焦点和引导线
- [ ] 色彩和谐，有主次之分
- [ ] 排版舒适（字重、行高、间距）
- [ ] 有交互反馈（悬停、点击、聚焦）
- [ ] 响应式美观（移动端、平板、桌面）
- [ ] 暗黑模式美观
- [ ] 符合WCAG 2.1 AA标准

---

## 三、Phase执行规范

### Phase 0：基础设施

**允许：**
- 仓库骨架
- 本地Docker栈
- 数据库迁移
- 契约定义
- 健康检查
- CI骨架

**禁止：**
- 场景特定的金镀层
- 未使用的提供者复杂性

**Skills要求：** 无特殊要求

### Phase 1：核心工作流

**允许：**
- BidPilot核心工作流
- 摄入、解析、检索、证据、起草

**禁止：**
- 高级场景扩展
- 超出占位符的生产认证和多租户设计

**Skills要求：**
- 必须使用 `langgraph-agent-patterns`

### Phase 2：审核和导出

**允许：**
- 审核工作流
- 审计可见性
- 导出管道
- 治理界面

**Skills要求：**
- 必须使用 `shadcn`（组件开发）
- 必须使用 `taste-skills`（设计审美）

### Phase 3：认证和运维

**允许：**
- 认证和RBAC
- 部署自动化
- 备份和恢复
- 加固和韧性

**Skills要求：** 无特殊要求

### Phase 4：场景扩展

**允许：**
- 受控复用平台核心用于新场景包

**Skills要求：**
- 必须使用 `langgraph-agent-patterns`（优化Agent协调）

---

## 四、文档优先级

当文档冲突时，按此优先级使用：

1. `docs/superpowers/specs/2026-04-18-docpilot-design.md`
2. `docs/product/mvp-scope.md`
3. `docs/product/roadmap.md`
4. 当前Phase计划（`docs/superpowers/plans/`）
5. ADR和架构文档
6. 工程、质量、安全、运维文档

**如果两个文档实质性冲突，暂停并更新文档后再继续实现。**

---

## 五、任务选择规则

**优先选择：**
- ✅ 解锁下一阶段依赖的任务
- ✅ 让验收场景通过的任务
- ✅ 减少长期架构漂移的任务
- ✅ 提升生产可信度的任务

**推迟：**
- ⏸️ 纯装饰但不阻塞的任务
- ⏸️ 投机性抽象
- ⏸️ BidPilot完成前的第二场景工作

---

## 六、文档更新规则

**必须在同一变更中更新文档：**
- 基础技术选择变更
- 引入新的API或事件族
- 运行手册或运维行为变更
- 非功能性目标变更
- 延迟的决策变得活跃

---

## 七、完成规则

**不要将任务标记为完成，除非：**
- ✅ 代码已实现
- ✅ 相关测试或冒烟检查已运行
- ✅ 文档仍然对齐
- ✅ 下一个实现者能知道什么变了、什么还在

---

## 八、阻塞处理

**当被未解决的决策阻塞时：**
1. 检查 `docs/product/open-decisions-and-risks.md`
2. 如果触发条件未满足，使用当前默认值
3. 如果触发条件已满足，先更新文档或留下精确的阻塞说明

---

## 九、快速参考

### 9.1 Skills触发条件速查

| 场景 | Skills | 命令 |
|------|--------|------|
| 实现LangGraph图 | `langgraph-agent-patterns` | 激活skill |
| 添加UI组件 | `shadcn` | `npx shadcn@latest add <name>` |
| 设计新页面 | `high-end-visual-design` | 激活skill |
| 代码审查 | `code-review` | 激活skill |
| 运行验证 | `verify` | 激活skill |

### 9.2 关键文件速查

**开发规范：**
- `docs/development/agent-execution-manual.md` - 执行手册
- `docs/development/current-execution-state.md` - 当前状态
- `docs/development/development-preflight-checklist.md` - Preflight检查

**后端LangGraph：**
- `services/worker/app/graph/builder.py` - 图定义
- `services/worker/app/graph/state.py` - 状态定义
- `services/worker/app/graph/nodes/` - Agent节点
- `docs/architecture/langgraph-agent.md` - LangGraph架构

**前端设计：**
- `apps/web/src/components/ui/` - shadcn组件
- `apps/web/src/index.css` - CSS变量和设计token
- `docs/architecture/frontend-application-architecture.md` - 前端架构
- `docs/product/frontend-experience-principles.md` - 设计原则

**数据模型：**
- `services/api/app/models.py` - SQLAlchemy模型
- `docs/architecture/data-model.md` - 数据模型文档

### 9.3 验证命令速查

```bash
# 后端
pytest                                    # 运行测试
alembic upgrade head                      # 数据库迁移
python scripts/validate_agent_graph.py    # LangGraph验证

# 前端
npm run typecheck                         # 类型检查
npm run test                              # 单元测试
npm run build                             # 构建
npm run storybook                         # Storybook

# Docker
docker compose up -d                      # 启动服务
docker compose down                       # 停止服务
```

---

## 十、设计原则摘要

参考：`docs/product/frontend-experience-principles.md`

### 视觉层次感
```css
/* ✅ 使用阴影和渐变创建深度 */
.hero {
    background: linear-gradient(135deg, oklch(0.55 0.15 250), oklch(0.65 0.12 270));
    box-shadow: 0 20px 25px -5px oklch(0 0 0 / 0.1);
}

/* ❌ 避免平面设计 */
.hero {
    background: #3b82f6;
}
```

### 精致细节
```css
/* ✅ 精致边框圆角 */
.card {
    border: 1px solid oklch(0.92 0.01 250);
    border-radius: 1rem;
    box-shadow: 0 4px 6px -1px oklch(0 0 0 / 0.06);
}
```

### 舒适间距
```tsx
/* ✅ 8px基准网格 */
<section className="space-y-8 px-6 py-12">
    <h2 className="text-3xl font-bold">标题</h2>
</section>
```

### 优雅动画
```tsx
/* ✅ 平滑过渡 */
<Button className="transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5">
    操作
</Button>
```

---

## 十一、LangGraph模式摘要

参考：`langgraph-agent-patterns` skill文档

### Supervisor模式
**适用：** 复杂工作流，需要LLM智能路由

```python
def supervisor_node(state: MyState) -> dict:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    # LLM决策下一个Agent
    return {"next": llm_decide_next(state)}
```

### Router模式
**适用：** 简单分类，确定性规则

```python
def router_node(state: MyState) -> str:
    if not state.get("requirements_parsed"):
        return "rfp_parser"
    if not state.get("evidence_retrieved"):
        return "knowledge_retriever"
    # ...
```

### Orchestrator-Worker模式
**适用：** 并行执行，需要聚合结果

```python
from langgraph.types import Send

def orchestrator(state: MyState) -> list[Send]:
    return [
        Send("worker", {"task": task})
        for task in decompose(state["task"])
    ]
```

### Handoffs模式
**适用：** 顺序工作流，逐步构建

```python
def agent_1(state: MyState) -> dict:
    result = process(state)
    return {"output": result, "next": "agent_2"}
```

---

## 安全红线

**绝对禁止将 API key、token、密码、secret 明文硬编码或提交到 git。**

- 所有密钥通过环境变量（`.env`，不入仓库）或 secrets manager 注入
- 代码中使用 `os.environ.get("KEY_NAME")` 读取，绝不写死值
- 提交前检查 diff 中有无意外的 key/token/secret
- 测试代码中的 mock key 使用明显占位符（如 `sk-test-placeholder-not-real`）
- 发现已泄露的 key 立即提醒轮换

---

## 最终原则

**Optimize for continuous, reviewable progress toward a production system, not bursts of impressive but disconnected implementation.**

为持续、可审查的生产系统进展优化，而不是为令人印象深刻但脱节的实现爆发优化。

---

**文档版本：** v1.0
**最后更新：** 2026-06-09
**维护者：** 五条老师团队
