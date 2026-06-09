# DocPilot LangGraph 实现评估与改进计划

## 一、当前实现评估

### 1.1 现有架构分析

**当前模式：** Supervisor（确定性路由）

**节点拓扑：**
```
__start__ → supervisor
  ├─→ rfp_parser
  ├─→ knowledge_retriever
  ├─→ section_drafter
  ├─→ quality_reviewer
  ├─→ human_approval (HITL)
  └─→ persist_result → __end__
```

**当前实现特点：**
- ✅ 7个专业节点
- ✅ PostgreSQL检查点
- ✅ Human-in-the-loop支持
- ✅ 迭代控制（max_iterations=3）
- ✅ 状态设计完整（BidPilotState）

### 1.2 问题诊断

#### ❌ **问题1：模式选择不当**
**现状：** 使用Supervisor模式，但supervisor节点只是确定性路由（纯状态检查，无LLM调用）

**根据langgraph-agent-patterns skill：**
- 确定性路由应该使用**Router模式**
- Supervisor模式应该有LLM智能决策
- 当前实现没有发挥Supervisor的真正价值

**证据：**
```python
def supervisor_node(state: BidPilotState) -> dict:
    """只是迭代计数，没有LLM路由决策"""
    current = state.get("iteration", 0)
    return {"iteration": current + 1}
```

#### ❌ **问题2：缺乏LLM智能路由**
**现状：** 所有路由都是基于状态标志的确定性检查

**影响：**
- 无法根据上下文动态调整流程
- 无法实现更智能的Agent协调
- 错过了Supervisor模式的核心价值

#### ⚠️ **问题3：并行能力未利用**
**现状：** 所有步骤都是串行执行

**改进机会：**
- RFP解析和知识检索可以并行（Orchestrator-Worker模式）
- 多个证据来源可以并行检索

#### ⚠️ **问题4：Agent历史未追踪**
**现状：** 没有记录哪些Agent被调用、调用顺序、耗时等

**影响：**
- 难以调试和优化
- 无法实现Agent级别的监控

---

## 二、改进方案

### 方案A：升级为LLM-Based Supervisor（推荐）

**目标：** 充分发挥Supervisor模式的优势

**改进内容：**

#### 1. **增强Supervisor节点**
```python
def supervisor_node(state: BidPilotState) -> dict:
    """LLM智能路由决策"""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = f"""作为BidPilot工作流的监督者，根据当前状态决定下一步：

当前状态：
- 项目ID: {state['project_id']}
- 章节: {state['section_key']}
- 迭代次数: {state.get('iteration', 0)}/{state.get('max_iterations', 3)}
- 需求已解析: {state.get('requirements_parsed', False)}
- 证据已检索: {state.get('evidence_retrieved', False)}
- 草稿已创建: {state.get('draft_created', False)}
- 审核通过: {state.get('review_passed', False)}
- 人工决策: {state.get('human_decision')}

可选下一步：
1. rfp_parser - 解析RFP文档
2. knowledge_retriever - 检索知识证据
3. section_drafter - 生成章节草稿
4. quality_reviewer - 质量审核
5. human_approval - 人工审核（HITL）
6. persist_result - 持久化结果

根据当前状态，选择最佳的下一步。考虑：
- 是否需要先解析需求？
- 证据是否充分？
- 草稿质量如何？
- 是否需要人工审核？
- 迭代次数是否已达上限？

请返回下一步的名称。"""

    response = llm.invoke(prompt)
    next_node = response.content.strip()

    # 验证返回的节点是否有效
    valid_nodes = ["rfp_parser", "knowledge_retriever", "section_drafter",
                   "quality_reviewer", "human_approval", "persist_result"]

    if next_node not in valid_nodes:
        # 降级到确定性路由
        next_node = deterministic_route(state)

    return {
        "next": next_node,
        "iteration": state.get("iteration", 0) + 1,
        "agent_history": state.get("agent_history", []) + [{
            "agent": "supervisor",
            "decision": next_node,
            "timestamp": datetime.now().isoformat()
        }]
    }
```

#### 2. **增强状态设计**
```python
class AgentCall(TypedDict):
    """记录Agent调用历史"""
    agent: str
    action: str
    timestamp: str
    duration_ms: int
    success: bool

class BidPilotState(TypedDict):
    # ... 现有字段 ...

    # 新增：Agent历史
    agent_history: list[AgentCall]

    # 新增：上下文摘要（避免状态过大）
    context_summary: str | None

    # 新增：错误追踪
    errors: list[str]
```

#### 3. **添加Orchestrator-Worker并行能力**

**改进knowledge_retriever为并行模式：**
```python
from langgraph.types import Send

def route_after_rfp(state: BidPilotState) -> list[Send]:
    """并行检索多个知识源"""
    sources = ["rfp_content", "previous_proposals", "company_knowledge"]

    return [
        Send("knowledge_retriever", {
            **state,
            "source_type": source
        })
        for source in sources
    ]
```

### 方案B：保持Router模式但增强（保守）

**适用场景：** 如果不需要LLM智能路由，只想保持确定性路由

**改进内容：**

#### 1. **添加Agent历史追踪**
```python
def route_initial(state: BidPilotState) -> tuple[str, dict]:
    """返回路由决策和更新的状态"""
    if not state.get("requirements_parsed"):
        return "rfp_parser", {
            "agent_history": state.get("agent_history", []) + [{
                "agent": "router",
                "decision": "rfp_parser",
                "reason": "requirements_not_parsed"
            }]
        }
    # ... 其他路由逻辑
```

#### 2. **添加并行检索能力**
```python
def knowledge_retriever_node(state: BidPilotState) -> dict:
    """并行检索多个知识源"""
    import asyncio

    async def retrieve_parallel():
        tasks = [
            retrieve_from_rfp(state),
            retrieve_from_previous_proposals(state),
            retrieve_from_company_knowledge(state)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if not isinstance(r, Exception)]

    evidence_chunks = asyncio.run(retrieve_parallel())

    return {
        "evidence_chunks": evidence_chunks,
        "evidence_retrieved": True
    }
```

---

## 三、推荐改进路径

### 阶段1：立即改进（1-2天）

**目标：** 增强现有实现，不改变基本架构

**任务清单：**

1. ✅ **添加Agent历史追踪**
   - 在状态中添加`agent_history`字段
   - 每个节点记录调用信息
   - 用于调试和监控

2. ✅ **增强日志和监控**
   - 添加LangSmith集成
   - 记录每个节点的耗时
   - 追踪错误和异常

3. ✅ **改进状态管理**
   - 添加context_summary避免状态过大
   - 实现状态压缩逻辑
   - 优化嵌入向量传递

4. ✅ **完善Human-in-the-loop**
   - 添加审批超时机制
   - 支持多级审批
   - 添加审批历史记录

### 阶段2：中期升级（3-5天）

**目标：** 升级为LLM-Based Supervisor

**任务清单：**

1. ✅ **实现LLM Supervisor**
   - 替换确定性路由为LLM决策
   - 添加路由决策的结构化输出
   - 实现降级机制（LLM失败时用确定性路由）

2. ✅ **添加Orchestrator-Worker能力**
   - 实现知识检索的并行化
   - 使用Send API实现fan-out
   - 添加结果聚合逻辑

3. ✅ **优化Agent协调**
   - 实现Agent间的上下文传递
   - 添加Agent级别的重试机制
   - 实现Agent负载均衡

4. ✅ **添加Agent监控**
   - 实现Agent级别的性能指标
   - 添加Agent调用链追踪
   - 实现Agent健康检查

### 阶段3：长期优化（1-2周）

**目标：** 实现完整的多Agent系统

**任务清单：**

1. ✅ **实现专业化Agent**
   - 添加专门的证据收集Agent
   - 添加专门的质量审核Agent
   - 添加专门的格式化Agent

2. ✅ **实现Agent学习**
   - 记录成功的路由决策
   - 实现路由策略的A/B测试
   - 基于历史数据优化路由

3. ✅ **实现分布式Agent**
   - 支持Agent的水平扩展
   - 实现Agent的负载均衡
   - 添加Agent的故障转移

---

## 四、具体实施计划

### 4.1 立即实施：Agent历史追踪

**修改文件：**
- `services/worker/app/graph/state.py` - 添加AgentCall类型
- `services/worker/app/graph/nodes/*.py` - 记录调用历史
- `services/worker/app/graph/builder.py` - 初始化状态

**代码示例：**

```python
# state.py
class AgentCall(TypedDict):
    agent: str
    action: str
    input_summary: str
    output_summary: str
    timestamp: str
    duration_ms: int
    success: bool
    error: str | None

class BidPilotState(TypedDict):
    # ... 现有字段 ...
    agent_history: Annotated[list[AgentCall], operator.add]
```

```python
# rfp_parser_node.py
import time
from datetime import datetime

def rfp_parser_node(state: BidPilotState) -> dict:
    start_time = time.time()

    try:
        # 执行RFP解析
        requirements = parse_rfp(state["project_id"], state["section_key"])

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "requirements": requirements,
            "requirements_parsed": True,
            "agent_history": [{
                "agent": "rfp_parser",
                "action": "parse_requirements",
                "input_summary": f"project={state['project_id']}, section={state['section_key']}",
                "output_summary": f"parsed {len(requirements)} requirements",
                "timestamp": datetime.now().isoformat(),
                "duration_ms": duration_ms,
                "success": True,
                "error": None
            }]
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "requirements_parsed": False,
            "error": str(e),
            "agent_history": [{
                "agent": "rfp_parser",
                "action": "parse_requirements",
                "input_summary": f"project={state['project_id']}, section={state['section_key']}",
                "output_summary": "failed",
                "timestamp": datetime.now().isoformat(),
                "duration_ms": duration_ms,
                "success": False,
                "error": str(e)
            }]
        }
```

### 4.2 中期实施：LLM Supervisor

**新增文件：**
- `services/worker/app/graph/nodes/llm_supervisor.py`

**代码示例：**

```python
# llm_supervisor.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

class SupervisorDecision(BaseModel):
    """监督者决策的结构化输出"""
    next_node: str = Field(description="下一个要执行的节点")
    reason: str = Field(description="决策原因")
    confidence: float = Field(description="决策置信度，0-1")

def create_llm_supervisor():
    """创建LLM监督者"""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}}
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是BidPilot工作流的监督者。根据当前状态决定下一步执行哪个Agent。

可选的Agent：
1. rfp_parser - 解析RFP文档，提取需求
2. knowledge_retriever - 检索相关知识证据
3. section_drafter - 生成章节草稿
4. quality_reviewer - 质量审核
5. human_approval - 人工审核（HITL）
6. persist_result - 持久化结果

决策规则：
- 如果需求未解析 → rfp_parser
- 如果证据未检索 → knowledge_retriever
- 如果草稿未创建 → section_drafter
- 如果草稿已创建但未审核 → quality_reviewer
- 如果审核通过 → human_approval
- 如果人工已批准 → persist_result
- 如果人工拒绝 → section_drafter（带反馈）
- 如果迭代次数达上限 → persist_result

考虑因素：
- 当前状态的完整性
- 迭代次数限制
- 错误状态
- 上下文信息

返回JSON格式：
{
    "next_node": "节点名称",
    "reason": "决策原因",
    "confidence": 0.95
}"""),
        ("human", """当前状态：
- 项目ID: {project_id}
- 章节: {section_key}
- 迭代次数: {iteration}/{max_iterations}
- 需求已解析: {requirements_parsed}
- 证据已检索: {evidence_retrieved}
- 草稿已创建: {draft_created}
- 审核通过: {review_passed}
- 人工决策: {human_decision}
- 错误: {error}

Agent历史：
{agent_history}

请决定下一步。""")
    ])

    chain = prompt | llm | StrOutputParser()

    return chain

def llm_supervisor_node(state: BidPilotState) -> dict:
    """LLM智能路由"""
    import json
    import time
    from datetime import datetime

    start_time = time.time()

    try:
        chain = create_llm_supervisor()

        # 准备输入
        agent_history_str = "\n".join([
            f"- {h['agent']}: {h['action']} ({h['duration_ms']}ms, success={h['success']})"
            for h in state.get("agent_history", [])[-5:]  # 只显示最近5条
        ])

        result = chain.invoke({
            "project_id": state["project_id"],
            "section_key": state["section_key"],
            "iteration": state.get("iteration", 0),
            "max_iterations": state.get("max_iterations", 3),
            "requirements_parsed": state.get("requirements_parsed", False),
            "evidence_retrieved": state.get("evidence_retrieved", False),
            "draft_created": state.get("draft_created", False),
            "review_passed": state.get("review_passed", False),
            "human_decision": state.get("human_decision"),
            "error": state.get("error"),
            "agent_history": agent_history_str or "无"
        })

        # 解析结果
        decision = json.loads(result)
        next_node = decision["next_node"]

        # 验证节点有效性
        valid_nodes = ["rfp_parser", "knowledge_retriever", "section_drafter",
                       "quality_reviewer", "human_approval", "persist_result"]

        if next_node not in valid_nodes:
            # 降级到确定性路由
            next_node = deterministic_route(state)

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "next": next_node,
            "iteration": state.get("iteration", 0) + 1,
            "agent_history": [{
                "agent": "supervisor",
                "action": "route_decision",
                "input_summary": f"iteration={state.get('iteration', 0)}",
                "output_summary": f"routed to {next_node} (confidence={decision.get('confidence', 0)})",
                "timestamp": datetime.now().isoformat(),
                "duration_ms": duration_ms,
                "success": True,
                "error": None
            }]
        }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)

        # 降级到确定性路由
        next_node = deterministic_route(state)

        return {
            "next": next_node,
            "iteration": state.get("iteration", 0) + 1,
            "error": f"LLM supervisor failed: {str(e)}",
            "agent_history": [{
                "agent": "supervisor",
                "action": "route_decision",
                "input_summary": f"iteration={state.get('iteration', 0)}",
                "output_summary": f"LLM failed, fallback to {next_node}",
                "timestamp": datetime.now().isoformat(),
                "duration_ms": duration_ms,
                "success": False,
                "error": str(e)
            }]
        }
```

---

## 五、前端改进计划

### 5.1 现状评估

**当前前端状态：**
- ✅ 使用shadcn/ui 4.3.1
- ✅ 有AI相关组件（chat-container, message, prompt-input）
- ✅ 有Agent状态流组件（agent-status-stream）
- ❌ 没有集成vercel-ai-sdk
- ⚠️ 可能没有应用taste-skills的设计理念

### 5.2 改进方案

#### **立即实施：应用taste-skills设计理念**

**目标：** 提升前端设计品质，避免AI设计的"slop"

**改进内容：**

1. **改进色彩系统**
   - 使用更精致的配色方案
   - 添加渐变和阴影层次
   - 实现暗黑模式优化

2. **改进排版**
   - 使用Geist字体系统
   - 优化字重和行高
   - 改善文本层次感

3. **改进组件设计**
   - 添加微交互和动画
   - 改善卡片和按钮设计
   - 优化表单和输入框

4. **改进布局**
   - 使用更精致的间距系统
   - 添加视觉分隔
   - 优化响应式设计

#### **中期实施：集成shadcn-ai组件库**

**目标：** 使用专业的AI组件库，提升AI交互体验

**集成组件：**

1. **聊天组件**
   - 使用shadcn-ai的Chat组件
   - 支持流式消息显示
   - 实现打字机效果

2. **Agent状态组件**
   - 使用shadcn-ai的Progress组件
   - 实现实时状态更新
   - 添加Agent节点可视化

3. **提示输入组件**
   - 使用shadcn-ai的Prompt组件
   - 支持自动补全
   - 实现提示建议

4. **AI表单组件**
   - 使用shadcn-ai的Form组件
   - 支持AI辅助填写
   - 实现智能验证

---

## 六、总结与建议

### 6.1 优先级排序

**P0（立即）：**
1. 添加Agent历史追踪
2. 增强日志和监控
3. 应用taste-skills设计理念

**P1（1周内）：**
1. 升级为LLM-Based Supervisor
2. 集成shadcn-ai组件库
3. 添加Orchestrator-Worker能力

**P2（2周内）：**
1. 实现Agent学习机制
2. 优化Agent监控
3. 添加分布式Agent支持

### 6.2 预期收益

**技术收益：**
- ✅ 更智能的路由决策
- ✅ 更好的可调试性
- ✅ 更高的并行能力
- ✅ 更强的容错能力

**业务收益：**
- ✅ 更快的文档处理速度
- ✅ 更高的草稿质量
- ✅ 更好的用户体验
- ✅ 更容易的运维监控

### 6.3 风险评估

**技术风险：**
- ⚠️ LLM调用增加延迟
- ⚠️ LLM成本增加
- ⚠️ LLM可能产生无效路由

**缓解措施：**
- 实现降级机制（LLM失败时用确定性路由）
- 使用更快的模型（gpt-4o-mini）
- 添加路由验证逻辑
- 实现路由缓存

---

## 七、下一步行动

### 立即行动（今天）：

1. ✅ 创建改进计划文档（本文档）
2. ✅ 评估当前实现的问题
3. ✅ 设计改进方案

### 本周行动：

1. ✅ 实现Agent历史追踪
2. ✅ 增强日志和监控
3. ✅ 改进前端设计系统

### 下周行动：

1. ✅ 实现LLM Supervisor
2. ✅ 集成shadcn-ai组件库
3. ✅ 添加并行检索能力

---

**生成时间：** 2026-06-09
**文档版本：** v1.0
**负责人：** 五条老师团队
