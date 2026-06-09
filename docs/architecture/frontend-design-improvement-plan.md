# DocPilot 前端设计改进计划

## 一、当前设计评估

### 1.1 现状分析

**技术栈：**
- ✅ React 19 + TypeScript
- ✅ Vite 7.0
- ✅ Tailwind CSS 4.2
- ✅ shadcn/ui 4.3.1
- ✅ Lucide React图标
- ✅ Geist字体

**组件使用：**
- ✅ 基础UI组件完整（Button, Card, Badge等）
- ✅ 有AI相关组件（chat-container, message, prompt-input）
- ✅ 有Agent状态流组件（agent-status-stream）
- ✅ 有命令面板（CommandPalette）
- ✅ 有国际化支持（i18next）

**设计系统：**
- ✅ CSS变量系统
- ✅ 设计token
- ✅ 暗黑模式支持（next-themes）
- ✅ 响应式设计

### 1.2 问题诊断

#### ⚠️ **问题1：缺乏高端设计感**
**现状：** 设计较为基础，缺乏精致感

**对比taste-skills的标准：**
- ❌ 缺乏视觉层次感
- ❌ 阴影和渐变使用不足
- ❌ 微交互和动画缺失
- ❌ 色彩搭配较为平淡

#### ⚠️ **问题2：AI交互体验一般**
**现状：** AI组件功能完整，但体验不够精致

**对比shadcn-ai的标准：**
- ❌ 没有流式消息显示
- ❌ 缺乏打字机效果
- ❌ Agent状态可视化不够直观
- ❌ 提示输入缺乏智能建议

#### ⚠️ **问题3：排版和间距需优化**
**现状：** 排版较为普通，间距系统不够精致

**对比high-end-visual-design的标准：**
- ❌ 字重层次不够明显
- ❌ 行高和间距不够舒适
- ❌ 文本对齐和留白需优化
- ❌ 视觉焦点不够突出

---

## 二、改进方案

### 方案A：应用taste-skills设计理念（推荐）

**目标：** 提升设计品质，避免AI设计的"slop"

**核心原则：**

1. **视觉层次感**
   - 使用阴影和渐变创建深度
   - 通过大小、颜色、字重建立层次
   - 添加视觉焦点和引导线

2. **精致的细节**
   - 微妙的边框和圆角
   - 精致的图标和装饰
   - 细腻的颜色过渡

3. **舒适的间距**
   - 使用8px基准网格
   - 垂直节奏一致性
   - 充足的留白空间

4. **优雅的动画**
   - 平滑的过渡效果
   - 恰当的动画时长
   - 自然的交互反馈

**具体改进：**

#### 1. **改进色彩系统**

```css
/* index.css - 改进后的色彩系统 */

@theme inline {
    /* 主色调：使用更精致的蓝色系 */
    --color-primary: oklch(0.55 0.15 250);  /* 深蓝色 */
    --color-primary-foreground: oklch(0.98 0.01 250);

    /* 强调色：温暖的橙色 */
    --color-accent: oklch(0.70 0.15 60);
    --color-accent-foreground: oklch(0.15 0.02 60);

    /* 背景色：微妙的灰色层次 */
    --color-background: oklch(0.99 0.005 250);
    --color-foreground: oklch(0.15 0.02 250);

    /* 表面色：添加深度 */
    --color-card: oklch(1 0 0);
    --color-card-foreground: oklch(0.15 0.02 250);

    /* 交互色：精致的反馈 */
    --color-muted: oklch(0.96 0.01 250);
    --color-muted-foreground: oklch(0.45 0.03 250);

    /* 边框色：微妙的分隔 */
    --color-border: oklch(0.92 0.01 250);
    --color-input: oklch(0.92 0.01 250);

    /* 状态色：清晰的反馈 */
    --color-destructive: oklch(0.60 0.20 25);
    --color-success: oklch(0.65 0.18 145);
    --color-warning: oklch(0.75 0.15 85);
}

/* 添加精致的阴影系统 */
@layer base {
    :root {
        --shadow-sm: 0 1px 2px oklch(0 0 0 / 0.04);
        --shadow-md: 0 4px 6px -1px oklch(0 0 0 / 0.06),
                     0 2px 4px -2px oklch(0 0 0 / 0.04);
        --shadow-lg: 0 10px 15px -3px oklch(0 0 0 / 0.08),
                     0 4px 6px -4px oklch(0 0 0 / 0.04);
        --shadow-xl: 0 20px 25px -5px oklch(0 0 0 / 0.10),
                     0 8px 10px -6px oklch(0 0 0 / 0.04);
    }
}

/* 添加精致的渐变 */
@layer utilities {
    .gradient-primary {
        background: linear-gradient(135deg,
            oklch(0.55 0.15 250) 0%,
            oklch(0.65 0.12 270) 100%);
    }

    .gradient-subtle {
        background: linear-gradient(180deg,
            oklch(1 0 0) 0%,
            oklch(0.98 0.005 250) 100%);
    }

    .gradient-card {
        background: linear-gradient(145deg,
            oklch(1 0 0) 0%,
            oklch(0.99 0.003 250) 100%);
    }
}
```

#### 2. **改进排版系统**

```css
/* index.css - 改进后的排版 */

@theme inline {
    /* 字体系统 */
    --font-sans: 'Geist Variable', -apple-system, BlinkMacSystemFont,
                 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    --font-mono: 'Geist Mono Variable', ui-monospace, SFMono-Regular,
                 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace;

    /* 字号系统：使用更舒适的尺寸 */
    --text-xs: 0.75rem;      /* 12px */
    --text-sm: 0.875rem;     /* 14px */
    --text-base: 1rem;       /* 16px */
    --text-lg: 1.125rem;     /* 18px */
    --text-xl: 1.25rem;      /* 20px */
    --text-2xl: 1.5rem;      /* 24px */
    --text-3xl: 1.875rem;    /* 30px */
    --text-4xl: 2.25rem;     /* 36px */

    /* 行高系统 */
    --leading-none: 1;
    --leading-tight: 1.25;
    --leading-snug: 1.375;
    --leading-normal: 1.5;
    --leading-relaxed: 1.625;
    --leading-loose: 2;

    /* 字重系统 */
    --font-weight-normal: 400;
    --font-weight-medium: 500;
    --font-weight-semibold: 600;
    --font-weight-bold: 700;
}

/* 应用排版优化 */
@layer base {
    h1 {
        font-size: var(--text-4xl);
        font-weight: var(--font-weight-bold);
        line-height: var(--leading-tight);
        letter-spacing: -0.025em;
    }

    h2 {
        font-size: var(--text-3xl);
        font-weight: var(--font-weight-semibold);
        line-height: var(--leading-tight);
        letter-spacing: -0.02em;
    }

    h3 {
        font-size: var(--text-2xl);
        font-weight: var(--font-weight-semibold);
        line-height: var(--leading-snug);
    }

    p {
        font-size: var(--text-base);
        font-weight: var(--font-weight-normal);
        line-height: var(--leading-relaxed);
    }

    small {
        font-size: var(--text-sm);
        line-height: var(--leading-normal);
    }
}
```

#### 3. **改进组件设计**

```tsx
// components/ui/button-improved.tsx

import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
    {
        variants: {
            variant: {
                default: "bg-primary text-primary-foreground shadow-md hover:bg-primary/90 hover:shadow-lg active:shadow-sm",
                destructive: "bg-destructive text-destructive-foreground shadow-md hover:bg-destructive/90 hover:shadow-lg",
                outline: "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground hover:shadow-md",
                secondary: "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80 hover:shadow-md",
                ghost: "hover:bg-accent hover:text-accent-foreground",
                link: "text-primary underline-offset-4 hover:underline",
            },
            size: {
                default: "h-10 px-4 py-2",
                sm: "h-9 rounded-md px-3",
                lg: "h-11 rounded-lg px-8",
                icon: "h-10 w-10",
            },
        },
        defaultVariants: {
            variant: "default",
            size: "default",
        },
    }
)

export interface ButtonProps
    extends React.ButtonHTMLAttributes<HTMLButtonElement>,
        VariantProps<typeof buttonVariants> {
    asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant, size, asChild = false, ...props }, ref) => {
        const Comp = asChild ? Slot : "button"
        return (
            <Comp
                className={cn(buttonVariants({ variant, size, className }))}
                ref={ref}
                {...props}
            />
        )
    }
)
Button.displayName = "Button"

export { Button, buttonVariants }
```

```tsx
// components/ui/card-improved.tsx

import * as React from "react"
import { cn } from "@/lib/utils"

const Card = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={cn(
            "rounded-xl border bg-card text-card-foreground shadow-md transition-shadow duration-200 hover:shadow-lg",
            className
        )}
        {...props}
    />
))
Card.displayName = "Card"

const CardHeader = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={cn("flex flex-col space-y-1.5 p-6", className)}
        {...props}
    />
))
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<
    HTMLParagraphElement,
    React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
    <h3
        ref={ref}
        className={cn("text-2xl font-semibold leading-none tracking-tight", className)}
        {...props}
    />
))
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<
    HTMLParagraphElement,
    React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
    <p
        ref={ref}
        className={cn("text-sm text-muted-foreground", className)}
        {...props}
    />
))
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
    <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
))
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={cn("flex items-center p-6 pt-0", className)}
        {...props}
    />
))
CardFooter.displayName = "CardFooter"

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
```

#### 4. **改进动画和交互**

```css
/* index.css - 添加动画系统 */

@layer utilities {
    /* 淡入动画 */
    .animate-fade-in {
        animation: fadeIn 0.3s ease-out;
    }

    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(4px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* 滑入动画 */
    .animate-slide-in {
        animation: slideIn 0.3s ease-out;
    }

    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateX(-8px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    /* 缩放动画 */
    .animate-scale-in {
        animation: scaleIn 0.2s ease-out;
    }

    @keyframes scaleIn {
        from {
            opacity: 0;
            transform: scale(0.95);
        }
        to {
            opacity: 1;
            transform: scale(1);
        }
    }

    /* 打字机效果 */
    .animate-typing {
        animation: typing 1s steps(3) infinite;
    }

    @keyframes typing {
        0%, 100% {
            opacity: 1;
        }
        50% {
            opacity: 0.3;
        }
    }

    /* 脉冲动画 */
    .animate-pulse-subtle {
        animation: pulseSubtle 2s ease-in-out infinite;
    }

    @keyframes pulseSubtle {
        0%, 100% {
            opacity: 1;
        }
        50% {
            opacity: 0.7;
        }
    }
}

/* 过渡效果优化 */
@layer base {
    * {
        transition-property: color, background-color, border-color,
                             text-decoration-color, fill, stroke, opacity,
                             box-shadow, transform, filter, backdrop-filter;
        transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
        transition-duration: 150ms;
    }

    button, a, input, select, textarea {
        transition-duration: 200ms;
    }
}
```

---

### 方案B：集成shadcn-ai组件库（中期）

**目标：** 使用专业的AI组件库，提升AI交互体验

**集成计划：**

#### 1. **安装shadcn-ai**

```bash
# 添加shadcn-ai组件
npx shadcn-ai@latest add chat
npx shadcn-ai@latest add prompt
npx shadcn-ai@latest add agent-status
```

#### 2. **集成聊天组件**

```tsx
// features/drafting/drafting-chat.tsx

import { Chat } from "@/components/ui/ai/chat"
import { ChatMessage } from "@/components/ui/ai/chat-message"
import { ChatInput } from "@/components/ui/ai/chat-input"

export function DraftingChat({ runId }: { runId: string }) {
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [isLoading, setIsLoading] = useState(false)

    const handleSubmit = async (message: string) => {
        setIsLoading(true)

        // 添加用户消息
        setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: "user",
            content: message,
            timestamp: new Date()
        }])

        // 调用API
        const response = await fetch(`/api/drafting/chat`, {
            method: "POST",
            body: JSON.stringify({ runId, message })
        })

        const data = await response.json()

        // 添加AI响应（支持流式）
        setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: "assistant",
            content: data.response,
            timestamp: new Date()
        }])

        setIsLoading(false)
    }

    return (
        <Chat className="h-[600px]">
            <ChatMessage.List>
                {messages.map(message => (
                    <ChatMessage key={message.id} message={message} />
                ))}
                {isLoading && (
                    <ChatMessage.Loading />
                )}
            </ChatMessage.List>
            <ChatInput
                onSubmit={handleSubmit}
                isLoading={isLoading}
                placeholder="输入修改建议或问题..."
            />
        </Chat>
    )
}
```

#### 3. **集成Agent状态组件**

```tsx
// components/agent-status-visual.tsx

import { AgentStatus } from "@/components/ui/ai/agent-status"
import { AgentProgress } from "@/components/ui/ai/agent-progress"
import { AgentTimeline } from "@/components/ui/ai/agent-timeline"

export function AgentStatusVisual({ runId }: { runId: string }) {
    const { state } = useAgentStream(runId)

    return (
        <AgentStatus className="w-full">
            <AgentStatus.Header>
                <AgentStatus.Title>Agent执行状态</AgentStatus.Title>
                <AgentStatus.Badge variant={state.isRunning ? "default" : "secondary"}>
                    {state.isRunning ? "执行中" : "已完成"}
                </AgentStatus.Badge>
            </AgentStatus.Header>

            <AgentProgress
                value={state.completedNodes.length}
                max={state.nodes.length}
                className="my-4"
            />

            <AgentTimeline>
                {state.nodes.map(node => (
                    <AgentTimeline.Item
                        key={node.name}
                        status={node.status}
                        name={node.name}
                        duration={node.duration}
                    />
                ))}
            </AgentTimeline>

            {state.isWaitingApproval && (
                <AgentStatus.Approval
                    message={state.approvalMessage}
                    onApprove={() => handleApproval("approved")}
                    onReject={(feedback) => handleApproval("rejected_with_feedback", feedback)}
                />
            )}
        </AgentStatus>
    )
}
```

#### 4. **集成提示输入组件**

```tsx
// components/prompt-input-improved.tsx

import { PromptInput } from "@/components/ui/ai/prompt-input"
import { PromptSuggestion } from "@/components/ui/ai/prompt-suggestion"

export function PromptInputImproved({
    onSubmit,
    isLoading
}: {
    onSubmit: (value: string) => void
    isLoading: boolean
}) {
    const suggestions = [
        "请优化这段文字的表达",
        "帮我补充更多细节",
        "检查是否有语法错误",
        "让语气更加正式"
    ]

    return (
        <PromptInput onSubmit={onSubmit} isLoading={isLoading}>
            <PromptInput.Textarea
                placeholder="输入修改建议或问题..."
                className="min-h-[100px]"
            />
            <PromptInput.Actions>
                <PromptInput.Submit disabled={isLoading}>
                    {isLoading ? "生成中..." : "发送"}
                </PromptInput.Submit>
            </PromptInput.Actions>
            <PromptSuggestion>
                {suggestions.map((suggestion, index) => (
                    <PromptSuggestion.Item
                        key={index}
                        onClick={() => onSubmit(suggestion)}
                    >
                        {suggestion}
                    </PromptSuggestion.Item>
                ))}
            </PromptSuggestion>
        </PromptInput>
    )
}
```

---

## 三、具体实施计划

### 3.1 立即实施（1-2天）

**任务清单：**

1. ✅ **改进色彩系统**
   - 更新index.css中的色彩变量
   - 添加阴影和渐变系统
   - 优化暗黑模式配色

2. ✅ **改进排版系统**
   - 更新字体和字号系统
   - 优化行高和间距
   - 改善文本层次感

3. ✅ **改进基础组件**
   - 更新Button组件（添加阴影和动画）
   - 更新Card组件（添加渐变和阴影）
   - 更新Input组件（改善交互反馈）

4. ✅ **添加动画系统**
   - 实现淡入、滑入、缩放动画
   - 添加打字机效果
   - 优化过渡效果

### 3.2 中期实施（3-5天）

**任务清单：**

1. ✅ **集成shadcn-ai组件库**
   - 安装和配置shadcn-ai
   - 集成聊天组件
   - 集成Agent状态组件
   - 集成提示输入组件

2. ✅ **改进AI交互体验**
   - 实现流式消息显示
   - 添加打字机效果
   - 优化Agent状态可视化

3. ✅ **改进页面设计**
   - 重新设计落地页
   - 优化项目详情页
   - 改进设置页面

4. ✅ **添加微交互**
   - 实现按钮悬停效果
   - 添加卡片展开动画
   - 优化表单交互反馈

### 3.3 长期优化（1-2周）

**任务清单：**

1. ✅ **实现设计系统文档**
   - 创建Storybook文档
   - 记录组件用法
   - 提供设计指南

2. ✅ **优化响应式设计**
   - 改进移动端布局
   - 优化平板端显示
   - 添加断点系统

3. ✅ **实现主题定制**
   - 支持主题切换
   - 添加自定义主题
   - 实现主题预设

4. ✅ **性能优化**
   - 优化组件渲染
   - 减少重绘重排
   - 实现懒加载

---

## 四、预期效果

### 4.1 视觉效果提升

**改进前：**
- 基础的平面设计
- 普通的阴影和边框
- 平淡的色彩搭配

**改进后：**
- 精致的立体设计
- 细腻的阴影和渐变
- 优雅的色彩层次

### 4.2 交互体验提升

**改进前：**
- 基础的悬停效果
- 普通的过渡动画
- 简单的状态反馈

**改进后：**
- 精致的微交互
- 流畅的动画效果
- 清晰的状态反馈

### 4.3 AI体验提升

**改进前：**
- 基础的聊天界面
- 简单的状态显示
- 普通的输入框

**改进后：**
- 流式消息显示
- 可视化Agent状态
- 智能提示建议

---

## 五、技术实现细节

### 5.1 改进CSS变量系统

```css
/* 新增的设计token */

:root {
    /* 间距系统 */
    --spacing-1: 0.25rem;  /* 4px */
    --spacing-2: 0.5rem;   /* 8px */
    --spacing-3: 0.75rem;  /* 12px */
    --spacing-4: 1rem;     /* 16px */
    --spacing-5: 1.25rem;  /* 20px */
    --spacing-6: 1.5rem;   /* 24px */
    --spacing-8: 2rem;     /* 32px */
    --spacing-10: 2.5rem;  /* 40px */
    --spacing-12: 3rem;    /* 48px */
    --spacing-16: 4rem;    /* 64px */

    /* 圆角系统 */
    --radius-sm: 0.375rem;  /* 6px */
    --radius-md: 0.5rem;    /* 8px */
    --radius-lg: 0.75rem;   /* 12px */
    --radius-xl: 1rem;      /* 16px */
    --radius-2xl: 1.5rem;   /* 24px */

    /* 动画时长 */
    --duration-fast: 150ms;
    --duration-normal: 200ms;
    --duration-slow: 300ms;

    /* 缓动函数 */
    --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
    --ease-out: cubic-bezier(0, 0, 0.2, 1);
    --ease-in: cubic-bezier(0.4, 0, 1, 1);
}
```

### 5.2 改进Tailwind配置

```typescript
// tailwind.config.ts

import type { Config } from "tailwindcss"

const config: Config = {
    content: [
        "./src/**/*.{ts,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                border: "hsl(var(--border))",
                input: "hsl(var(--input))",
                ring: "hsl(var(--ring))",
                background: "hsl(var(--background))",
                foreground: "hsl(var(--foreground))",
                primary: {
                    DEFAULT: "hsl(var(--primary))",
                    foreground: "hsl(var(--primary-foreground))",
                },
                secondary: {
                    DEFAULT: "hsl(var(--secondary))",
                    foreground: "hsl(var(--secondary-foreground))",
                },
                destructive: {
                    DEFAULT: "hsl(var(--destructive))",
                    foreground: "hsl(var(--destructive-foreground))",
                },
                muted: {
                    DEFAULT: "hsl(var(--muted))",
                    foreground: "hsl(var(--muted-foreground))",
                },
                accent: {
                    DEFAULT: "hsl(var(--accent))",
                    foreground: "hsl(var(--accent-foreground))",
                },
                popover: {
                    DEFAULT: "hsl(var(--popover))",
                    foreground: "hsl(var(--popover-foreground))",
                },
                card: {
                    DEFAULT: "hsl(var(--card))",
                    foreground: "hsl(var(--card-foreground))",
                },
            },
            borderRadius: {
                lg: "var(--radius)",
                md: "calc(var(--radius) - 2px)",
                sm: "calc(var(--radius) - 4px)",
            },
            fontFamily: {
                sans: ["var(--font-sans)"],
                mono: ["var(--font-mono)"],
            },
            keyframes: {
                "accordion-down": {
                    from: { height: "0" },
                    to: { height: "var(--radix-accordion-content-height)" },
                },
                "accordion-up": {
                    from: { height: "var(--radix-accordion-content-height)" },
                    to: { height: "0" },
                },
                "fade-in": {
                    from: { opacity: "0", transform: "translateY(4px)" },
                    to: { opacity: "1", transform: "translateY(0)" },
                },
                "slide-in": {
                    from: { opacity: "0", transform: "translateX(-8px)" },
                    to: { opacity: "1", transform: "translateX(0)" },
                },
                "scale-in": {
                    from: { opacity: "0", transform: "scale(0.95)" },
                    to: { opacity: "1", transform: "scale(1)" },
                },
            },
            animation: {
                "accordion-down": "accordion-down 0.2s ease-out",
                "accordion-up": "accordion-up 0.2s ease-out",
                "fade-in": "fade-in 0.3s ease-out",
                "slide-in": "slide-in 0.3s ease-out",
                "scale-in": "scale-in 0.2s ease-out",
            },
        },
    },
    plugins: [require("tailwindcss-animate")],
}

export default config
```

---

## 六、总结

### 6.1 改进价值

**设计品质：**
- ✅ 从基础设计升级为高端设计
- ✅ 建立专业的视觉层次
- ✅ 实现精致的细节处理

**用户体验：**
- ✅ 提升交互流畅度
- ✅ 增强视觉反馈
- ✅ 改善AI交互体验

**品牌形象：**
- ✅ 提升专业感
- ✅ 增强信任度
- ✅ 改善用户留存

### 6.2 实施优先级

**P0（立即）：**
1. 改进色彩和排版系统
2. 更新基础组件设计
3. 添加动画系统

**P1（1周内）：**
1. 集成shadcn-ai组件库
2. 改进AI交互体验
3. 优化页面设计

**P2（2周内）：**
1. 实现设计系统文档
2. 优化响应式设计
3. 实现主题定制

---

**生成时间：** 2026-06-09
**文档版本：** v1.0
**负责人：** 五条老师团队
