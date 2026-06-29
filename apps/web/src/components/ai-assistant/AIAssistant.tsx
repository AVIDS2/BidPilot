import { useState, useRef, useEffect, useCallback } from "react";
import { MessageCircleIcon, XIcon, SparklesIcon, SendIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export function AIAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { t } = useTranslation("ai-assistant");

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 发送消息
  const handleSend = useCallback(async (text?: string) => {
    const content = text ?? input;
    if (!content.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: content.trim(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    const aiMessage: ChatMessage = {
      id: `ai-${Date.now()}`,
      role: "assistant",
      content: "",
    };
    setMessages(prev => [...prev, aiMessage]);

    try {
      const token = localStorage.getItem("BidPilot_token");
      const response = await fetch("http://localhost:8000/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message: content.trim(),
          conversation_history: messages.map(m => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "content" && data.content) {
                setMessages(prev =>
                  prev.map(msg =>
                    msg.id === aiMessage.id
                      ? { ...msg, content: msg.content + data.content }
                      : msg
                  )
                );
              }
            } catch {
              // Skip invalid JSON
            }
          }
        }
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages(prev =>
        prev.map(msg =>
          msg.id === aiMessage.id
            ? { ...msg, content: "抱歉，发生了错误，请稍后重试。" }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, messages]);

  // 快捷操作
  const quickActions = [
    { label: t("actions.createProject"), action: "帮我创建一个新项目" },
    { label: t("actions.howToUse"), action: "怎么使用BidPilot？" },
    { label: t("actions.generateSection"), action: "帮我生成执行摘要" },
  ];

  return (
    <>
      {/* 悬浮按钮 - 棱镜彩效果 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full",
          "flex items-center justify-center",
          "transition-all duration-300 hover:scale-110",
          "shadow-lg hover:shadow-xl",
          isOpen ? "rotate-90" : ""
        )}
        style={{
          background: "linear-gradient(135deg, #84cc16, #22d3ee, #a78bfa, #f472b6)",
          backgroundSize: "300% 300%",
          animation: "gradient-shift 3s ease infinite",
        }}
      >
        {isOpen ? (
          <XIcon className="w-6 h-6 text-white" />
        ) : (
          <SparklesIcon className="w-6 h-6 text-white" />
        )}
      </button>

      {/* 棱镜彩渐变动画 */}
      <style>{`
        @keyframes gradient-shift {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
      `}</style>

      {/* 对话窗口 */}
      {isOpen && (
        <div
          className="fixed bottom-24 right-6 z-50 w-96 h-[500px] rounded-2xl shadow-2xl flex flex-col overflow-hidden"
          style={{
            background: "var(--card)",
            border: "1px solid var(--border)",
          }}
        >
          {/* 头部 - 棱镜彩渐变 */}
          <div
            className="flex items-center justify-between p-4"
            style={{
              background: "linear-gradient(135deg, #84cc16, #22d3ee, #a78bfa)",
              backgroundSize: "200% 200%",
              animation: "gradient-shift 3s ease infinite",
            }}
          >
            <div className="flex items-center gap-2">
              <SparklesIcon className="w-5 h-5 text-white" />
              <span className="font-medium text-white">{t("title")}</span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-white/80 hover:text-white transition-colors"
            >
              <XIcon className="w-5 h-5" />
            </button>
          </div>

          {/* 消息列表 */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              // 欢迎消息
              <div className="text-center py-8">
                <div
                  className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
                  style={{
                    background: "linear-gradient(135deg, #84cc16, #22d3ee, #a78bfa)",
                    backgroundSize: "200% 200%",
                    animation: "gradient-shift 3s ease infinite",
                  }}
                >
                  <SparklesIcon className="w-8 h-8 text-white" />
                </div>
                <h3 className="font-medium mb-2" style={{ color: "var(--foreground)" }}>
                  {t("welcome.title")}
                </h3>
                <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                  {t("welcome.description")}
                </p>
              </div>
            ) : (
              // 消息列表
              messages.map(message => (
                <div
                  key={message.id}
                  className={cn(
                    "flex",
                    message.role === "user" ? "justify-end" : "justify-start"
                  )}
                >
                  <div
                    className={cn(
                      "max-w-[80%] rounded-2xl px-4 py-2",
                      message.role === "user" ? "rounded-br-md" : "rounded-bl-md"
                    )}
                    style={{
                      background: message.role === "user"
                        ? "linear-gradient(135deg, #84cc16, #22d3ee)"
                        : "var(--muted)",
                      color: message.role === "user" ? "white" : "var(--foreground)",
                    }}
                  >
                    {message.content || (isLoading && message.id.startsWith("ai-") ? (
                      <span className="animate-pulse">●●●</span>
                    ) : null)}
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* 快捷操作 */}
          {messages.length === 0 && (
            <div className="px-4 pb-2 flex flex-wrap gap-2">
              {quickActions.map((action, index) => (
                <button
                  key={index}
                  onClick={() => handleSend(action.action)}
                  className="text-xs px-3 py-1.5 rounded-full transition-all duration-200 hover:scale-105"
                  style={{
                    background: "var(--muted)",
                    color: "var(--muted-foreground)",
                    border: "1px solid var(--border)",
                  }}
                >
                  {action.label}
                </button>
              ))}
            </div>
          )}

          {/* 输入框 */}
          <div className="p-4 border-t" style={{ borderColor: "var(--border)" }}>
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                placeholder={t("inputPlaceholder")}
                className="flex-1 px-4 py-2 rounded-xl text-sm outline-none"
                style={{
                  background: "var(--muted)",
                  color: "var(--foreground)",
                  border: "1px solid var(--border)",
                }}
                disabled={isLoading}
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || isLoading}
                className="w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200"
                style={{
                  background: input.trim()
                    ? "linear-gradient(135deg, #84cc16, #22d3ee)"
                    : "var(--muted)",
                  color: input.trim() ? "white" : "var(--muted-foreground)",
                }}
              >
                <SendIcon className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
