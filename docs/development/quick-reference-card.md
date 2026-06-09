# DocPilot 开发快速参考卡片

## 🚀 一、开发前必读

### 1.1 Preflight检查清单
```bash
# 检查环境
shell: powershell
python: conda activate llm

# 检查服务
docker ps | grep docpilot-postgres  # 端口5433
docker ps | grep docpilot-redis     # 端口6379
docker ps | grep docpilot-minio     # 端口9000/9001

# 检查当前Phase
cat docs/development/current-execution-state.md
```

### 1.2 必读文档
```bash
# 通用
docs/development/agent-execution-manual.md
docs/development/development-preflight-checklist.md

# 后端LangGraph
docs/architecture/langgraph-agent.md
docs/architecture/backend-application-architecture.md

# 前端设计
docs/architecture/frontend-application-architecture.md
docs/product/frontend-experience-principles.md
```

---

## 🤖 二、后端开发（LangGraph）

### 2.1 Skills触发条件
```
✅ 使用langgraph-agent-patterns的情况：
├─ 实现新的LangGraph图
├─ 修改Agent节点
├─ 变更路由逻辑
├─ 优化多Agent协调
└─ 调试Agent问题
```

### 2.2 Agent模式选择速查表

| 场景 | 模式 | 关键特征 |
|------|------|---------|
| 复杂工作流，需要动态路由 | **Supervisor** | LLM智能决策，根据上下文选择Agent |
| 简单分类，一次性路由 | **Router** | 确定性规则，无需LLM |
| 任务可并行，需要聚合结果 | **Orchestrator-Worker** | Send API fan-out，结果list reducer |
| 清晰顺序，逐步构建 | **Handoffs** | 上下文传递，每个Agent在前一个基础上工作 |

### 2.3 状态设计模板

```python
from typing import Annotated, TypedDict
import operator

class AgentCall(TypedDict):
    agent: str
    action: str
    duration_ms: int
    success: bool
    error: str | None

class MyState(TypedDict):
    # 输入
    project_id: str

    # Agent输出（每个Agent一组）
    requirements: list[dict]
    requirements_parsed: bool

    # 控制流
    iteration: int
    max_iterations: int
    error: str | None

    # Agent历史（必须！）
    agent_history: Annotated[list[AgentCall], operator.add]
```

### 2.4 Agent节点模板

```python
def my_agent_node(state: MyState) -> dict:
    import time
    from datetime import datetime

    start_time = time.time()

    try:
        # 1. 执行逻辑
        result = do_something(state)

        # 2. 计算耗时
        duration_ms = int((time.time() - start_time) * 1000)

        # 3. 返回结果 + 历史
        return {
            "output_field": result,
            "success_flag": True,
            "agent_history": [{
                "agent": "my_agent",
                "action": "do_something",
                "duration_ms": duration_ms,
                "success": True,
                "error": None
            }]
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)

        # 4. 错误处理 + 历史
        return {
            "error": str(e),
            "agent_history": [{
                "agent": "my_agent",
                "action": "do_something",
                "duration_ms": duration_ms,
                "success": False,
                "error": str(e)
            }]
        }
```

### 2.5 LLM Supervisor模板

```python
def supervisor_node(state: MyState) -> dict:
    from langchain_openai import ChatOpenAI
    import json

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = f"""根据当前状态决定下一步Agent：

当前状态：
- 项目: {state['project_id']}
- 迭代: {state.get('iteration', 0)}/{state.get('max_iterations', 3)}
- 需求已解析: {state.get('requirements_parsed', False)}
- 证据已检索: {state.get('evidence_retrieved', False)}

可选Agent: rfp_parser, knowledge_retriever, section_drafter, quality_reviewer, persist_result

返回JSON: {{"next": "agent_name", "reason": "原因"}}"""

    try:
        response = llm.invoke(prompt)
        decision = json.loads(response.content)

        return {
            "next": decision["next"],
            "iteration": state.get("iteration", 0) + 1
        }
    except Exception:
        # 降级到确定性路由
        return deterministic_route(state)
```

### 2.6 图组装模板

```python
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.postgres import PostgresSaver

def build_graph() -> StateGraph:
    sg = StateGraph(MyState)

    # 注册节点
    sg.add_node("supervisor", supervisor_node)
    sg.add_node("agent_1", agent_1_node)
    sg.add_node("agent_2", agent_2_node)

    # 入口
    sg.set_entry_point("supervisor")

    # 条件边
    sg.add_conditional_edges(
        "supervisor",
        route_function,
        {"agent_1": "agent_1", "agent_2": "agent_2"}
    )

    # 普通边
    sg.add_edge("agent_1", "supervisor")
    sg.add_edge("agent_2", END)

    return sg

# 编译（必须用检查点）
graph = build_graph().compile(
    checkpointer=PostgresSaver.from_conn_string(database_url),
    interrupt_before=["human_approval"]  # HITL
)
```

### 2.7 验证命令

```bash
# 验证图结构
python scripts/validate_agent_graph.py services/worker/app/graph/builder.py:graph

# 可视化图
python scripts/visualize_graph.py services/worker/app/graph/builder.py:graph -o graph.md

# 运行测试
pytest services/worker/tests/test_graph*.py -v
```

---

## 🎨 三、前端开发

### 3.1 Skills触发条件

```
✅ 使用shadcn的情况：
├─ 添加新UI组件
├─ 修改现有组件
├─ 集成第三方组件库
└─ 解决组件问题

✅ 使用taste-skills的情况：
├─ 设计新页面
├─ 重大UI改版
├─ 提升视觉品质
└─ 优化用户体验
```

### 3.2 shadcn组件使用

```bash
# 搜索组件
npx shadcn@latest search button

# 查看组件信息
npx shadcn@latest info card

# 添加组件
npx shadcn@latest add dialog

# 查看所有可用组件
npx shadcn@latest list
```

### 3.3 组件使用规范

```tsx
// ✅ 正确：使用shadcn组件
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function MyComponent() {
    return (
        <Card>
            <CardHeader>
                <CardTitle>标题</CardTitle>
            </CardHeader>
            <CardContent>
                <Button variant="default">操作</Button>
            </CardContent>
        </Card>
    )
}

// ❌ 错误：自定义基础组件
export function MyComponent() {
    return (
        <div className="my-card">
            <button className="my-button">操作</button>
        </div>
    )
}
```

### 3.4 设计原则速查

#### 视觉层次感
```css
/* ✅ 阴影和渐变 */
.hero {
    background: linear-gradient(135deg, oklch(0.55 0.15 250), oklch(0.65 0.12 270));
    box-shadow: 0 20px 25px -5px oklch(0 0 0 / 0.1);
}

/* ❌ 纯色平面 */
.hero {
    background: #3b82f6;
}
```

#### 精致细节
```css
/* ✅ 精致边框圆角 */
.card {
    border: 1px solid oklch(0.92 0.01 250);
    border-radius: 1rem;
    box-shadow: 0 4px 6px -1px oklch(0 0 0 / 0.06);
}

/* ❌ 粗糙细节 */
.card {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}
```

#### 舒适间距
```tsx
/* ✅ 8px基准网格 */
<section className="space-y-8 px-6 py-12">
    <h2 className="text-3xl font-bold">标题</h2>
</section>

/* ❌ 随意间距 */
<section className="space-y-5 px-5 py-10">
    <h2 className="text-2xl">标题</h2>
</section>
```

#### 优雅动画
```tsx
/* ✅ 平滑过渡 */
<Button className="transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5">
    操作
</Button>

/* ❌ 突兀变化 */
<Button className="hover:bg-blue-600">
    操作
</Button>
```

### 3.5 设计检查清单

每个页面/组件必须通过：

- [ ] **视觉层次**：有清晰的视觉焦点
- [ ] **色彩和谐**：配色协调有主次
- [ ] **排版舒适**：字重行高间距合适
- [ ] **交互反馈**：悬停点击聚焦有反馈
- [ ] **响应式**：多端显示美观
- [ ] **暗黑模式**：支持且美观
- [ ] **无障碍**：WCAG 2.1 AA

---

## 📋 四、Phase执行速查

### Phase 0：基础设施
```
✅ 允许：仓库骨架、Docker栈、迁移、契约、健康检查、CI
❌ 禁止：场景金镀层、未使用的提供者复杂性
🔧 Skills：无特殊要求
```

### Phase 1：核心工作流
```
✅ 允许：BidPilot工作流、摄入、解析、检索、证据、起草
❌ 禁止：高级场景扩展、生产认证多租户
🔧 Skills：langgraph-agent-patterns
```

### Phase 2：审核和导出
```
✅ 允许：审核工作流、审计、导出、治理界面
❌ 禁止：超出Phase 2范围的功能
🔧 Skills：shadcn, taste-skills
```

### Phase 3：认证和运维
```
✅ 允许：认证、RBAC、备份恢复、运维仪表板
❌ 禁止：超出Phase 3范围的功能
🔧 Skills：无特殊要求
```

### Phase 4：场景扩展
```
✅ 允许：场景包、模板绑定、契约测试
❌ 禁止：超出Phase 4范围的功能
🔧 Skills：langgraph-agent-patterns
```

---

## 🔍 五、快速验证

### 5.1 后端验证

```bash
# 测试
pytest tests/ -v

# LangGraph验证
python scripts/validate_agent_graph.py services/worker/app/graph/builder.py:graph

# 数据库迁移
alembic upgrade head
alembic check
```

### 5.2 前端验证

```bash
# 类型检查
npm run typecheck

# 测试
npm run test

# 构建
npm run build

# Storybook
npm run storybook
```

### 5.3 设计验证

```bash
# 在Storybook中检查
npm run storybook
# 访问 http://localhost:6006

# 响应式测试
# Chrome DevTools → 切换设备

# 暗黑模式
# 切换主题检查

# 无障碍
# axe DevTools 或 Lighthouse
```

---

## 🚨 六、常见问题速查

### 6.1 LangGraph问题

```bash
# 问题：图验证失败
解决：python scripts/validate_agent_graph.py <path>

# 问题：无限循环
解决：检查max_iterations和终止条件

# 问题：Agent路由错误
解决：检查route_function逻辑，使用LangSmith追踪

# 问题：检查点丢失
解决：检查PostgreSQL连接和PostgresSaver配置
```

### 6.2 前端问题

```bash
# 问题：组件样式错误
解决：检查是否正确使用shadcn组件

# 问题：响应式布局问题
解决：使用Tailwind断点系统（sm:, md:, lg:, xl:）

# 问题：暗黑模式不生效
解决：检查ThemeProvider和CSS变量

# 问题：动画卡顿
解决：使用CSS transform，避免重绘重排
```

### 6.3 设计问题

```bash
# 问题：视觉层次不清晰
解决：使用阴影、渐变、大小对比创建层次

# 问题：间距不舒适
解决：使用8px基准网格，保持一致性

# 问题：色彩不和谐
解决：使用设计token，参考taste-skills配色

# 问题：交互无反馈
解决：添加hover、focus、active状态
```

---

## 📞 七、关键资源

### 7.1 重要文件

```bash
# 配置
.env                                    # 环境变量
compose.yml                            # Docker配置
pyproject.toml                         # Python配置
apps/web/package.json                  # 前端配置

# 入口
services/api/app/main.py               # API入口
services/worker/app/graph/builder.py   # LangGraph图
apps/web/src/app.tsx                   # 前端入口

# 文档
CLAUDE.md                              # 开发Workflow（本文件）
docs/development/current-execution-state.md
docs/architecture/langgraph-agent.md
docs/architecture/frontend-application-architecture.md
```

### 7.2 Skills位置

```bash
~/.claude/skills/
├─ langgraph-agent-patterns/     # LangGraph模式
├─ langgraph-docs/               # LangGraph文档
├─ shadcn/                       # 组件库
├─ high-end-visual-design/       # 高端设计
├─ design-taste-frontend/        # 前端审美
├─ code-review/                  # 代码审查
└─ verify/                       # 验证
```

### 7.3 常用命令速查

```bash
# 后端
pytest                                    # 测试
alembic upgrade head                      # 迁移
celery -A app.celery_app worker           # Worker

# 前端
npm run dev                               # 开发
npm run test                              # 测试
npm run build                             # 构建
npm run storybook                         # Storybook

# LangGraph
python scripts/validate_agent_graph.py    # 验证图
python scripts/visualize_graph.py         # 可视化

# Docker
docker compose up -d                      # 启动
docker compose down                       # 停止
docker compose logs -f                    # 日志
```

---

## ✨ 八、开发最佳实践

### 8.1 代码规范

```python
# Python
- 使用type hints
- 遵循PEP 8
- 编写docstrings
- 优先使用dataclass/TypedDict
```

```tsx
// TypeScript
- 使用strict模式
- 定义interface/types
- 优先使用const
- 避免any
```

### 8.2 Git规范

```bash
# 提交信息格式
<type>(<scope>): <subject>

# 类型
feat:     新功能
fix:      修复bug
docs:     文档
style:    格式
refactor: 重构
test:     测试
chore:    杂项

# 示例
feat(graph): 添加LLM Supervisor节点
fix(api): 修复认证token刷新问题
docs(readme): 更新开发文档
```

### 8.3 测试规范

```bash
# 单元测试：每个函数/组件
# 集成测试：每个模块
# E2E测试：每个用户流程
# 覆盖率：>80%
```

---

## 🎯 九、快速决策树

### 开发任务类型判断

```
任务 → 是后端吗？
  ├─ 是 → 涉及LangGraph吗？
  │       ├─ 是 → 使用langgraph-agent-patterns
  │       └─ 否 → 遵循后端最佳实践
  └─ 否 → 是前端吗？
          ├─ 是 → 涉及UI组件吗？
          │       ├─ 是 → 使用shadcn
          │       └─ 否 → 涉及设计吗？
          │               ├─ 是 → 使用taste-skills
          │               └─ 否 → 遵循前端最佳实践
          └─ 否 → 遵循通用最佳实践
```

---

**文档版本：** v1.0
**快速参考卡片**
**打印后放在工位随时查阅！** 📋✨
