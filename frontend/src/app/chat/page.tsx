"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import {
  Send,
  Loader2,
  Sparkles,
  StopCircle,
  ChevronDown,
  Plus,
  MessageSquare,
  Trash2,
  Paperclip,
} from "lucide-react";
import AgentBadge from "@/components/AgentBadge";
import AgentStepCard from "@/components/AgentStepCard";
import AgentFlowVisualizer from "@/components/AgentFlowVisualizer";
import FileUploader from "@/components/FileUploader";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import {
  submitTaskStream,
  getExamples,
  getConversations,
  createConversation,
  getConversationMessages,
  saveMessage,
  deleteConversation,
  uploadFile,
  type StreamEvent,
  type AgentStep,
  type ExampleTask,
  type UploadResponse,
  type Conversation,
} from "@/lib/api";

interface Attachment {
  filename: string;
  url: string;
  size: number;
  type: string; // file extension like "png", "csv", "pdf"
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  attachments?: Attachment[];
  agentSteps?: AgentStep[];
  reportHtml?: string;
  agentOutputs?: Record<string, string>;
  iterations?: number;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentSteps, setCurrentSteps] = useState<AgentStep[]>([]);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [examples, setExamples] = useState<ExampleTask[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<UploadResponse[]>([]);
  const [showReport, setShowReport] = useState<string | null>(null);
  const [abortController, setAbortController] =
    useState<AbortController | null>(null);

  // Conversation management
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [showConversations, setShowConversations] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const searchParams = useSearchParams();

  // Load conversation from URL query param (e.g., /chat?conversation=abc)
  useEffect(() => {
    const convoId = searchParams.get("conversation");
    if (convoId && convoId !== activeConversationId) {
      handleLoadConversation(convoId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Load examples
  useEffect(() => {
    getExamples()
      .then(setExamples)
      .catch(() => {});
  }, []);

  // Load conversations
  useEffect(() => {
    getConversations()
      .then(setConversations)
      .catch(() => {});
  }, []);

  const handleNewConversation = useCallback(() => {
    setActiveConversationId(null);
    setMessages([]);
    setCurrentSteps([]);
    setActiveAgent(null);
  }, []);

  const handleLoadConversation = useCallback(async (convoId: string) => {
    try {
      const savedMessages = await getConversationMessages(convoId);
      const loaded: ChatMessage[] = savedMessages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        timestamp: new Date(m.created_at),
        attachments: (m.metadata as Record<string, unknown>)?.attachments as Attachment[] | undefined,
        agentSteps: (m.metadata as Record<string, unknown>)?.agent_steps as AgentStep[] | undefined,
        reportHtml: (m.metadata as Record<string, unknown>)?.report_html as string | undefined,
        agentOutputs: (m.metadata as Record<string, unknown>)?.agent_outputs as Record<string, string> | undefined,
        iterations: (m.metadata as Record<string, unknown>)?.iterations as number | undefined,
      }));
      setMessages(loaded);
      setActiveConversationId(convoId);
      setShowConversations(false);
    } catch {
      // silently fail
    }
  }, []);

  const handleDeleteConversation = useCallback(
    async (convoId: string) => {
      try {
        await deleteConversation(convoId);
        setConversations((prev) => prev.filter((c) => c.id !== convoId));
        if (activeConversationId === convoId) {
          handleNewConversation();
        }
      } catch {
        // silently fail
      }
    },
    [activeConversationId, handleNewConversation]
  );

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentSteps]);

  // Auto-resize textarea
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInput(e.target.value);
      e.target.style.height = "auto";
      e.target.style.height = Math.min(e.target.scrollHeight, 200) + "px";
    },
    []
  );

  // Handle paste — upload clipboard images/files
  const handlePaste = useCallback(
    async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      const items = e.clipboardData?.items;
      if (!items) return;

      const files: File[] = [];
      for (const item of Array.from(items)) {
        if (item.kind === "file") {
          const file = item.getAsFile();
          if (file) files.push(file);
        }
      }
      if (files.length === 0) return;

      // Prevent the default paste (don't paste binary garbage into textarea)
      e.preventDefault();

      try {
        const results: UploadResponse[] = [];
        for (const file of files) {
          const res = await uploadFile(file);
          results.push(res);
        }
        setUploadedFiles((prev) => [...prev, ...results]);
      } catch (err) {
        console.error("Paste upload failed:", err);
      }
    },
    []
  );

  const handleSubmit = useCallback(
    async (taskText?: string) => {
      const text = taskText || input.trim();
      if (!text || isLoading) return;

      // Create or reuse conversation
      let convoId = activeConversationId;
      if (!convoId) {
        try {
          const title = text.length > 60 ? text.slice(0, 60) + "..." : text;
          const convo = await createConversation(title);
          convoId = convo.id;
          setActiveConversationId(convoId);
          setConversations((prev) => [convo, ...prev]);
        } catch {
          // Continue without persistence
        }
      }

      // Build attachments from uploaded files
      const attachments: Attachment[] = uploadedFiles
        .filter((f) => f.url)
        .map((f) => ({
          filename: f.filename,
          url: f.url!,
          size: f.size,
          type: f.type || f.filename.split(".").pop() || "file",
        }));

      // Add user message
      const userMsg: ChatMessage = {
        id: Date.now().toString(),
        role: "user",
        content: text,
        timestamp: new Date(),
        attachments: attachments.length > 0 ? attachments : undefined,
      };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setIsLoading(true);
      setCurrentSteps([]);
      setActiveAgent(null);

      // Clear uploaded files after sending
      setUploadedFiles([]);

      // Persist user message with attachment metadata
      if (convoId) {
        saveMessage(convoId, {
          role: "user",
          content: text,
          metadata: attachments.length > 0 ? { attachments } : undefined,
        }).catch(() => {});
      }

      // Reset textarea height
      if (inputRef.current) {
        inputRef.current.style.height = "auto";
      }

      // Build conversation history from existing messages for context
      const conversationHistory = messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({ role: m.role, content: m.content }));

      const persistConvoId = convoId;
      const controller = submitTaskStream(
        {
          task: text,
          generate_html: true,
          file_ids: uploadedFiles.map((f) => f.upload_id),
          conversation_history: conversationHistory,
        },
        // onEvent
        (event: StreamEvent) => {
          switch (event.type) {
            case "start":
              setActiveAgent("project_manager");
              break;

            case "step":
              if (event.agent) {
                setActiveAgent(event.agent);
                setCurrentSteps((prev) => [
                  ...prev,
                  {
                    agent: event.agent!,
                    summary: event.summary || "",
                    tool_calls: event.tool_calls || 0,
                    status: "completed",
                  },
                ]);
              }
              break;

            case "done":
              setIsLoading(false);
              setActiveAgent(null);

              const assistantMsg: ChatMessage = {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: event.output || "Analysis complete.",
                timestamp: new Date(),
                agentSteps: event.agent_steps,
                reportHtml: event.report_html || undefined,
                agentOutputs: event.agent_outputs,
                iterations: event.iterations,
              };
              setMessages((prev) => [...prev, assistantMsg]);
              setCurrentSteps([]);

              // Persist assistant message with metadata
              if (persistConvoId) {
                saveMessage(persistConvoId, {
                  role: "assistant",
                  content: event.output || "Analysis complete.",
                  metadata: {
                    agent_steps: event.agent_steps,
                    report_html: event.report_html,
                    agent_outputs: event.agent_outputs,
                    iterations: event.iterations,
                  },
                }).catch(() => {});
              }
              break;

            case "error":
              setIsLoading(false);
              setActiveAgent(null);
              setCurrentSteps([]);

              const errorMsg: ChatMessage = {
                id: (Date.now() + 1).toString(),
                role: "system",
                content: `Error: ${event.message}`,
                timestamp: new Date(),
              };
              setMessages((prev) => [...prev, errorMsg]);
              break;
          }
        },
        // onError
        (error) => {
          setIsLoading(false);
          setActiveAgent(null);
          setCurrentSteps([]);

          const errorMsg: ChatMessage = {
            id: (Date.now() + 1).toString(),
            role: "system",
            content: `Connection error: ${error.message}`,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, errorMsg]);
        },
        // onComplete
        () => {
          setIsLoading(false);
          setActiveAgent(null);
        }
      );

      setAbortController(controller);
    },
    [input, isLoading, uploadedFiles, activeConversationId, messages]
  );

  const handleStop = useCallback(() => {
    abortController?.abort();
    setIsLoading(false);
    setActiveAgent(null);
    setCurrentSteps([]);
  }, [abortController]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  // Empty state
  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex flex-col h-full">
        {/* History toggle — top right */}
        {conversations.length > 0 && (
          <div className="flex justify-end px-4 py-2 pl-14 md:pl-4">
            <button
              onClick={() => setShowConversations(!showConversations)}
              className="flex items-center gap-2 text-sm text-muted hover:text-foreground transition-colors cursor-pointer"
            >
              <MessageSquare className="w-4 h-4" />
              <span className="hidden sm:inline">History ({conversations.length})</span>
              <span className="sm:hidden">History ({conversations.length})</span>
            </button>
          </div>
        )}

        {/* History sidebar panel — slides from right */}
        {showConversations && (
          <>
            <div className="fixed inset-0 z-40 bg-black/40" onClick={() => setShowConversations(false)} />
            <div className="fixed top-0 right-0 z-50 h-full w-72 sm:w-80 bg-surface border-l border-white/[0.06] shadow-2xl flex flex-col">
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
                <h3 className="text-sm font-semibold text-foreground">History</h3>
                <button onClick={() => setShowConversations(false)} className="text-muted hover:text-white transition-colors cursor-pointer p-1"><Plus className="w-4 h-4 rotate-45" /></button>
              </div>
              <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
                {conversations.map((convo) => (
                  <div
                    key={convo.id}
                    onClick={() => handleLoadConversation(convo.id)}
                    className="flex items-center justify-between group px-3 py-2.5 rounded-lg hover:bg-white/[0.04] transition-colors cursor-pointer"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-foreground truncate">{convo.title || "Untitled conversation"}</p>
                      <p className="text-xs text-muted">{new Date(convo.updated_at).toLocaleDateString()} {new Date(convo.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteConversation(convo.id); }}
                      className="md:opacity-0 md:group-hover:opacity-100 p-2 sm:p-1 text-muted hover:text-error transition-all cursor-pointer flex-shrink-0"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        <div className="flex-1 flex flex-col items-center justify-center px-4 sm:px-6 pt-6 sm:pt-0">
          <div className="max-w-2xl w-full text-center">
            <div className="flex items-center justify-center w-12 sm:w-16 h-12 sm:h-16 rounded-xl sm:rounded-2xl bg-white/[0.04] mx-auto mb-4 sm:mb-6 glow-border">
              <Sparkles className="w-6 sm:w-8 h-6 sm:h-8 text-white/60" />
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-white mb-2">
              What would you like to research?
            </h2>
            <p className="text-white/30 mb-6 sm:mb-8 text-xs sm:text-sm">
              Cecil AI coordinates multiple specialist agents to deliver
              comprehensive financial analysis.
            </p>

            {/* Example tasks — show 3 on mobile, all on desktop */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3 mb-6 sm:mb-8">
              {examples.map((ex, i) => (
                <button
                  key={ex.name}
                  onClick={() => handleSubmit(ex.task)}
                  className={`text-left p-4 rounded-xl border border-white/[0.04] bg-white/[0.02] hover:border-white/[0.1] hover:bg-white/[0.04] transition-all group glow-border-hover cursor-pointer ${i >= 3 ? "hidden sm:block" : ""}`}
                >
                  <h3 className="text-sm font-medium text-foreground group-hover:text-white transition-colors mb-1">
                    {ex.name.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                  </h3>
                  <p className="text-xs text-muted line-clamp-2">
                    {ex.description}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Input area at bottom */}
        <div className="border-t border-white/[0.06] p-3 sm:p-4">
          <div className="max-w-3xl mx-auto">
            <FileUploader files={uploadedFiles} onFilesChange={setUploadedFiles} />
            <div className="mt-2 sm:mt-3 flex gap-2 sm:gap-3">
              <textarea
                ref={inputRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder="Describe your research task..."
                rows={1}
                className="flex-1 resize-none rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 sm:px-4 py-3 text-sm text-foreground placeholder:text-white/20 focus:outline-none focus:border-white/[0.12] focus:ring-1 focus:ring-white/[0.06]"
              />
              <button
                onClick={() => handleSubmit()}
                disabled={!input.trim()}
                className="flex items-center justify-center w-11 h-11 rounded-xl bg-white/[0.08] text-white/80 border border-white/[0.06] disabled:opacity-20 disabled:cursor-not-allowed hover:bg-white/[0.15] transition-all glow-border-hover cursor-pointer"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Conversation header */}
      <div className="border-b border-white/[0.06] px-4 py-2 flex items-center justify-between bg-surface/40 backdrop-blur-sm pl-14 md:pl-4">
        <button
          onClick={handleNewConversation}
          className="flex items-center gap-1.5 text-sm text-muted hover:text-white transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">New Chat</span>
          <span className="sm:hidden">New</span>
        </button>
        <button
          onClick={() => setShowConversations(!showConversations)}
          className="flex items-center gap-2 text-sm text-muted hover:text-foreground transition-colors cursor-pointer"
        >
          <MessageSquare className="w-4 h-4" />
          <span className="hidden sm:inline">{conversations.length > 0
            ? `History (${conversations.length})`
            : "History"}</span>
          <span className="sm:hidden">{conversations.length > 0 ? `History (${conversations.length})` : "History"}</span>
        </button>
      </div>

      {/* History sidebar panel — slides from right */}
      {showConversations && (
        <>
          <div className="fixed inset-0 z-40 bg-black/40" onClick={() => setShowConversations(false)} />
          <div className="fixed top-0 right-0 z-50 h-full w-72 sm:w-80 bg-surface border-l border-white/[0.06] shadow-2xl flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
              <h3 className="text-sm font-semibold text-foreground">History</h3>
              <button onClick={() => setShowConversations(false)} className="text-muted hover:text-white transition-colors cursor-pointer p-1"><Plus className="w-4 h-4 rotate-45" /></button>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
              {conversations.map((convo) => (
                <div
                  key={convo.id}
                  onClick={() => handleLoadConversation(convo.id)}
                  className={`flex items-center justify-between group px-3 py-2.5 rounded-lg hover:bg-white/[0.04] transition-colors cursor-pointer ${
                    activeConversationId === convo.id ? "bg-white/[0.06] border border-white/[0.08]" : ""
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-foreground truncate">{convo.title || "Untitled conversation"}</p>
                    <p className="text-xs text-muted">{new Date(convo.updated_at).toLocaleDateString()} {new Date(convo.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteConversation(convo.id); }}
                    className="md:opacity-0 md:group-hover:opacity-100 p-2 sm:p-1 text-muted hover:text-error transition-all cursor-pointer flex-shrink-0"
                  >
                  <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-3 sm:px-4 py-4 sm:py-6">
        <div className="max-w-3xl mx-auto space-y-4 sm:space-y-6">
          {messages.map((msg) => (
            <div key={msg.id}>
              {msg.role === "user" ? (
                <div className="flex justify-end">
                  <div className="max-w-[90%] sm:max-w-[80%] px-3 sm:px-4 py-2.5 sm:py-3 rounded-2xl rounded-br-md bg-white/[0.06] border border-white/[0.08]">
                    <p className="text-sm text-foreground whitespace-pre-wrap">
                      {msg.content}
                    </p>
                    {/* Attached files */}
                    {msg.attachments && msg.attachments.length > 0 && (
                      <div className="mt-2 space-y-2">
                        {msg.attachments.map((att, i) => {
                          const isImage = ["png", "jpg", "jpeg", "gif", "webp"].includes(att.type);
                          return isImage ? (
                            <a
                              key={i}
                              href={att.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="block"
                            >
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={att.url}
                                alt={att.filename}
                                className="max-w-[240px] max-h-[180px] rounded-lg border border-white/[0.1] object-cover hover:border-white/30 transition-colors"
                              />
                              <span className="text-[10px] text-muted mt-0.5 block">
                                {att.filename}
                              </span>
                            </a>
                          ) : (
                            <a
                              key={i}
                              href={att.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-white/[0.03] border border-white/[0.06] text-xs hover:bg-white/[0.06] transition-colors w-fit"
                            >
                              <Paperclip className="w-3 h-3 text-white/50" />
                              <span className="text-foreground max-w-[160px] truncate">
                                {att.filename}
                              </span>
                              <span className="text-muted">
                                ({(att.size / 1024).toFixed(1)}KB)
                              </span>
                            </a>
                          );
                        })}
                      </div>
                    )}
                    <p className="text-xs text-muted mt-1">
                      {msg.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ) : msg.role === "system" ? (
                <div className="flex justify-center">
                  <div className="px-4 py-2 rounded-lg bg-error/10 border border-error/20 text-sm text-error">
                    {msg.content}
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Agent collaboration flow */}
                  {msg.agentSteps && msg.agentSteps.length > 0 && (
                    <div className="space-y-3">
                      <AgentFlowVisualizer steps={msg.agentSteps} />
                      <div className="space-y-2">
                        {msg.agentSteps.map((step, i) => (
                          <AgentStepCard key={i} step={step} index={i} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Final output */}
                    <div className="rounded-2xl rounded-bl-md bg-surface/60 border border-white/[0.06] p-3 sm:p-5 glow-border">
                    <div className="flex items-center gap-2 mb-3">
                      <AgentBadge
                        agent="project_manager"
                        size="sm"
                      />
                      <span className="text-xs text-muted">
                        Final Analysis
                        {msg.iterations
                          ? ` • ${msg.iterations} iterations`
                          : ""}
                      </span>
                    </div>
                    <MarkdownRenderer content={msg.content} />

                    {/* Report button */}
                    {msg.reportHtml && (
                      <div className="mt-4 pt-3 border-t border-border">
                        <button
                          onClick={() =>
                            setShowReport(
                              showReport === msg.id ? null : msg.id
                            )
                          }
                          className="flex items-center gap-2 text-sm text-white/60 hover:text-white transition-colors cursor-pointer"
                        >
                          <ChevronDown className={`w-4 h-4 transition-transform ${showReport === msg.id ? 'rotate-180' : ''}`} />
                          {showReport === msg.id
                            ? "Hide Full Report"
                            : "View Full Report"}
                        </button>
                        {showReport === msg.id && (
                          <div className="mt-3 rounded-lg border border-border overflow-hidden">
                            <iframe
                              srcDoc={msg.reportHtml}
                              className="w-full h-[400px] sm:h-[600px] bg-white"
                              title="Cecil AI Report"
                            />
                          </div>
                        )}
                      </div>
                    )}

                    <p className="text-xs text-muted mt-3">
                      {msg.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Loading state with live agent steps */}
          {isLoading && (
            <div className="space-y-4">
              {currentSteps.length > 0 && (
                <AgentFlowVisualizer
                  steps={currentSteps}
                  activeAgent={activeAgent || undefined}
                />
              )}
              {currentSteps.map((step, i) => (
                <AgentStepCard
                  key={i}
                  step={step}
                  index={i}
                  isActive={step.agent === activeAgent}
                />
              ))}
              <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-surface/60 border border-white/[0.06]">
                <Loader2 className="w-4 h-4 text-white/60 animate-spin" />
                <span className="text-sm text-muted">
                  {activeAgent ? (
                    <>
                      <AgentBadge
                        agent={activeAgent}
                        size="sm"
                        showLabel
                      />{" "}
                      is working...
                    </>
                  ) : (
                    "Thinking..."
                  )}
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="border-t border-white/[0.06] p-3 sm:p-4">
        <div className="max-w-3xl mx-auto">
          <FileUploader files={uploadedFiles} onFilesChange={setUploadedFiles} />
          <div className="mt-2 sm:mt-3 flex gap-2 sm:gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder={
                isLoading
                  ? "Waiting for analysis..."
                  : "Ask a follow-up question..."
              }
              rows={1}
              disabled={isLoading}
              className="flex-1 resize-none rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 sm:px-4 py-3 text-sm text-foreground placeholder:text-white/20 focus:outline-none focus:border-white/[0.12] focus:ring-1 focus:ring-white/[0.06] disabled:opacity-30"
            />
            {isLoading ? (
              <button
                onClick={handleStop}
                className="flex items-center justify-center w-11 h-11 rounded-xl bg-error/20 text-error border border-error/20 hover:bg-error/30 transition-colors cursor-pointer"
              >
                <StopCircle className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={() => handleSubmit()}
                disabled={!input.trim()}
                className="flex items-center justify-center w-11 h-11 rounded-xl bg-white/[0.08] text-white/80 border border-white/[0.06] disabled:opacity-20 disabled:cursor-not-allowed hover:bg-white/[0.15] transition-all glow-border-hover cursor-pointer"
              >
                <Send className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
