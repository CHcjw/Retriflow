import { computed, nextTick, ref, shallowRef } from "vue";

import {
  cancelChatStreamTask,
  createSession,
  deleteSession,
  fetchChatBootstrap,
  fetchSessionMessages,
  fetchSessions,
  streamChatMessage,
  submitMessageFeedback,
  updateSession,
  type ChatMcpCallItem,
  type ChatSourceItem,
  type ChatWorkflow
} from "../services/chatApi";

export interface ChatMessage {
  id: string;
  backendId?: number;
  role: "assistant" | "user";
  content: string;
  state: "complete" | "error" | "stopped" | "streaming";
  thinkingContent?: string;
  thinkingState?: "complete" | "streaming";
  thinkingStartedAt?: number;
  thinkingEndedAt?: number;
  feedbackVote?: 1 | -1;
  feedbackState?: "idle" | "saving" | "saved" | "error";
}

type RequestPhase = "idle" | "retrieving" | "stopping" | "streaming";
type StreamStage = "idle" | "analyzing" | "retrieving" | "organizing" | "answering" | "stopping";

interface ChatSessionRuntimeState {
  messages: ChatMessage[];
  latestSources: ChatSourceItem[];
  latestWorkflow: ChatWorkflow | null;
  latestMcpCalls: ChatMcpCallItem[];
  loading: boolean;
  requestPhase: RequestPhase;
  streamStage: StreamStage;
  errorMessage: string;
  infoMessage: string;
  lastSubmittedQuestion: string;
  lastSubmittedDeepThinking: boolean;
  lastSubmittedSmartSearch: boolean;
  activeStreamController: AbortController | null;
  activeStreamTaskId: string;
}

function createRuntimeState(): ChatSessionRuntimeState {
  return {
    messages: [],
    latestSources: [],
    latestWorkflow: null,
    latestMcpCalls: [],
    loading: false,
    requestPhase: "idle",
    streamStage: "idle",
    errorMessage: "",
    infoMessage: "",
    lastSubmittedQuestion: "",
    lastSubmittedDeepThinking: false,
    lastSubmittedSmartSearch: false,
    activeStreamController: null,
    activeStreamTaskId: ""
  };
}

const emptyRuntimeState = createRuntimeState();

function buildMessage(
  role: ChatMessage["role"],
  content: string,
  state: ChatMessage["state"] = "complete",
  backendId?: number
): ChatMessage {
  return {
    id: `${role}-${crypto.randomUUID()}`,
    backendId,
    role,
    content,
    state,
    feedbackState: "idle"
  };
}

function splitStreamingSegments(value: string): string[] {
  const text = value ?? "";
  if (!text) {
    return [];
  }

  const segments: string[] = [];
  let buffer = "";

  for (let index = 0; index < text.length; index += 1) {
    const current = text[index];
    const next = text[index + 1] ?? "";
    buffer += current;

    if (current === "\n" && next === "\n") {
      buffer += next;
      index += 1;
      segments.push(buffer);
      buffer = "";
      continue;
    }

    if (/[。！？.!?]/.test(current)) {
      segments.push(buffer);
      buffer = "";
      continue;
    }

    if (/[，、；;:：]/.test(current) && buffer.trim().length >= 8) {
      segments.push(buffer);
      buffer = "";
      continue;
    }

    if (buffer.length >= 20) {
      segments.push(buffer);
      buffer = "";
    }
  }

  if (buffer) {
    segments.push(buffer);
  }

  return segments.filter((segment) => segment.length > 0);
}

function getSegmentDelay(segment: string, index: number): number {
  const value = segment.trimEnd();
  if (!value) {
    return 18;
  }
  if (index === 0) {
    return 120;
  }
  if (/\n\n$/.test(segment)) {
    return 165;
  }
  if (/[。！？.!?]$/.test(value)) {
    return 96;
  }
  if (/[；:：;]$/.test(value)) {
    return 74;
  }
  if (/[，、]$/.test(value)) {
    return 48;
  }
  return Math.min(38, 14 + value.length * 2);
}

function splitThinkingSegments(value: string): string[] {
  const segments: string[] = [];
  for (const char of value) {
    segments.push(char);
  }
  return segments;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function normalizeForFinalComparison(value: string): string {
  return value.replace(/\s+/g, "").trim();
}

export function useRetriFlowChat() {
  const sessions = ref<Awaited<ReturnType<typeof fetchSessions>>["items"]>([]);
  const activeSessionId = shallowRef("");
  const sessionStates = ref<Record<string, ChatSessionRuntimeState>>({});
  const starterPrompts = ref<string[]>([
    "询问助手是做什么的、是谁、能做什么等",
    "今天广州天气如何",
    "帮我总结一下当前项目的 RAG 流程。"
  ]);

  const getSessionState = (sessionId: string): ChatSessionRuntimeState => {
    if (!sessionId) {
      return emptyRuntimeState;
    }
    if (!sessionStates.value[sessionId]) {
      sessionStates.value = {
        ...sessionStates.value,
        [sessionId]: createRuntimeState()
      };
    }
    return sessionStates.value[sessionId];
  };

  const activeState = computed(() => sessionStates.value[activeSessionId.value] ?? emptyRuntimeState);
  const messages = computed(() => activeState.value.messages);
  const latestSources = computed(() => activeState.value.latestSources);
  const latestWorkflow = computed(() => activeState.value.latestWorkflow);
  const latestMcpCalls = computed(() => activeState.value.latestMcpCalls);
  const loading = computed(() => activeState.value.loading);
  const errorMessage = computed(() => activeState.value.errorMessage);
  const requestPhase = computed(() => activeState.value.requestPhase);

  const statusText = computed(() => {
    const state = activeState.value;
    if (state.requestPhase === "stopping" || state.streamStage === "stopping") {
      return "正在停止本次回答...";
    }
    if (state.loading) {
      if (state.streamStage === "analyzing") {
        return "正在理解你的问题...";
      }
      if (state.streamStage === "retrieving") {
        return "正在检索相关资料...";
      }
      if (state.streamStage === "organizing") {
        return "正在整理参考内容...";
      }
      if (state.streamStage === "answering") {
        return "正在生成回答...";
      }
      return "正在准备回答...";
    }
    return state.errorMessage || state.infoMessage || "";
  });

  const hasMessages = computed(() => activeState.value.messages.length > 0);
  const canRetry = computed(() => Boolean(activeState.value.lastSubmittedQuestion.trim()) && !activeState.value.loading);
  const canStop = computed(() => activeState.value.loading && activeState.value.activeStreamController !== null);

  const touchKnownSessionStates = () => {
    for (const session of sessions.value) {
      getSessionState(session.id);
    }
  };

  const loadSessions = async () => {
    const data = await fetchSessions();
    sessions.value = data.items;
    touchKnownSessionStates();
    if (!sessions.value.find((item) => item.id === activeSessionId.value) && sessions.value[0]) {
      activeSessionId.value = sessions.value[0].id;
    }
    if (!sessions.value[0]) {
      activeSessionId.value = "";
    }
  };

  const loadMessages = async (sessionId = activeSessionId.value, options: { force?: boolean } = {}) => {
    if (!sessionId) {
      return;
    }
    const state = getSessionState(sessionId);
    if (state.loading && !options.force) {
      return;
    }
    const data = await fetchSessionMessages(sessionId);
    state.messages = data.items.map((item) => buildMessage(item.role, item.content, "complete", item.id));
  };

  const selectSession = async (sessionId: string) => {
    activeSessionId.value = sessionId;
    const state = getSessionState(sessionId);
    state.errorMessage = "";
    if (!state.loading) {
      state.infoMessage = "";
      state.requestPhase = "idle";
      state.streamStage = "idle";
      await loadMessages(sessionId);
    }
  };

  const createNewSession = async () => {
    const previousActiveSessionId = activeSessionId.value;
    const nextTitle = `RetriFlow 新会话 ${sessions.value.length + 1}`;

    try {
      const created = await createSession(nextTitle);
      getSessionState(created.id);
      activeSessionId.value = created.id;
      sessions.value = [created, ...sessions.value.filter((session) => session.id !== created.id)];
      const state = getSessionState(created.id);
      state.messages = [];
      state.latestSources = [];
      state.latestWorkflow = null;
      state.latestMcpCalls = [];
      state.errorMessage = "";
      state.infoMessage = "新会话已创建，可以直接开始提问。";
      state.requestPhase = "idle";
      state.streamStage = "idle";
      await loadSessions();
      activeSessionId.value = created.id;
    } catch (error) {
      activeSessionId.value = previousActiveSessionId;
      const state = getSessionState(previousActiveSessionId);
      state.errorMessage = error instanceof Error ? error.message : "新建会话失败，请稍后再试。";
    }
  };

  const removeSession = async (sessionId: string) => {
    const wasActiveSession = activeSessionId.value === sessionId;
    const previousSessions = sessions.value;
    sessions.value = sessions.value.filter((session) => session.id !== sessionId);
    try {
      await deleteSession(sessionId);
      const { [sessionId]: _removed, ...rest } = sessionStates.value;
      sessionStates.value = rest;
      await loadSessions();
      if (wasActiveSession) {
        await loadMessages(activeSessionId.value);
      }
    } catch (error) {
      sessions.value = previousSessions;
      const state = getSessionState(activeSessionId.value);
      state.errorMessage = error instanceof Error ? error.message : "删除会话失败，请稍后再试。";
    }
  };

  const renameSession = async (sessionId: string, title: string) => {
    if (!title.trim()) {
      return;
    }
    await updateSession(sessionId, title);
    await loadSessions();
  };

  const loadStarterPrompts = async () => {
    try {
      const bootstrap = await fetchChatBootstrap();
      const configuredPrompts = (bootstrap.starter_prompts ?? [])
        .map((prompt) => prompt.trim())
        .filter(Boolean);
      starterPrompts.value = Array.from(new Set(configuredPrompts)).slice(0, 6);
      if (starterPrompts.value.length === 0) {
        starterPrompts.value = [
          "询问助手是做什么的、是谁、能做什么等",
          "今天广州天气如何",
          "帮我总结一下当前项目的 RAG 流程。"
        ];
      }
    } catch {
      starterPrompts.value = [
        "询问助手是做什么的、是谁、能做什么等",
        "今天广州天气如何",
        "帮我总结一下当前项目的 RAG 流程。"
      ];
    }
  };

  const ask = async (question: string, options: { deepThinking?: boolean; smartSearch?: boolean } = {}) => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      return;
    }

    if (!activeSessionId.value) {
      await createNewSession();
    }
    const streamSessionId = activeSessionId.value;
    if (!streamSessionId) {
      return;
    }

    const state = getSessionState(streamSessionId);
    if (state.loading) {
      state.infoMessage = "当前会话正在生成回答，请先停止或切换到新会话。";
      return;
    }

    state.loading = true;
    state.requestPhase = "retrieving";
    state.streamStage = "analyzing";
    state.errorMessage = "";
    state.infoMessage = "";
    state.lastSubmittedQuestion = trimmedQuestion;
    state.lastSubmittedDeepThinking = Boolean(options.deepThinking);
    state.lastSubmittedSmartSearch = Boolean(options.smartSearch);
    state.latestSources = [];
    state.latestWorkflow = null;
    state.latestMcpCalls = [];
    state.messages = [...state.messages, buildMessage("user", trimmedQuestion)];

    try {
      const assistantMessage = buildMessage("assistant", "", "streaming");
      const controller = new AbortController();
      state.activeStreamController = controller;
      state.messages = [...state.messages, assistantMessage];

      let hasStreamedVisibleText = false;
      let thinkingQueue = Promise.resolve();
      const seenThinkingLines = new Set<string>();

      const appendThinkingLine = (line: string) => {
        if (!options.deepThinking || !line.trim() || seenThinkingLines.has(line)) {
          return;
        }
        seenThinkingLines.add(line);
        if (!assistantMessage.thinkingStartedAt) {
          assistantMessage.thinkingStartedAt = Date.now();
          assistantMessage.thinkingState = "streaming";
        }
        thinkingQueue = thinkingQueue.then(async () => {
          for (const segment of splitThinkingSegments(`${line}\n`)) {
            assistantMessage.thinkingContent = `${assistantMessage.thinkingContent ?? ""}${segment}`;
            state.messages = [...state.messages];
            await nextTick();
            await sleep(segment === "\n" ? 120 : 16);
          }
        });
      };

      const finishThinking = async () => {
        if (!options.deepThinking || assistantMessage.thinkingState !== "streaming") {
          return;
        }
        await thinkingQueue;
        assistantMessage.thinkingState = "complete";
        assistantMessage.thinkingEndedAt = Date.now();
        state.messages = [...state.messages];
      };

      appendThinkingLine("我先读取会话记忆，理解你的问题。");

      const renderStreamSegments = async (content: string) => {
        const segments = splitStreamingSegments(content);
        if (segments.length === 0) {
          return;
        }

        state.requestPhase = "streaming";
        state.streamStage = "answering";
        assistantMessage.state = "streaming";

        if (!hasStreamedVisibleText) {
          hasStreamedVisibleText = true;
          await sleep(72);
        }

        for (const [index, segment] of segments.entries()) {
          assistantMessage.content = `${assistantMessage.content}${segment}`;
          state.messages = [...state.messages];
          await nextTick();
          await sleep(getSegmentDelay(segment, index));
        }
      };

      await streamChatMessage(
        streamSessionId,
        trimmedQuestion,
        {
          onTask: async (payload) => {
            state.activeStreamTaskId = payload.task_id;
          },
          onWorkflow: async (workflow) => {
            state.latestWorkflow = workflow;
            if (state.streamStage === "analyzing") {
              state.streamStage = workflow.retrieval_count > 0 ? "retrieving" : "organizing";
            }
            const stages = (workflow.pipeline_stages ?? []).join(" → ");
            appendThinkingLine(stages ? `链路阶段：${stages}。` : "正在完成问题重写、意图识别和路由判断。");
            if (workflow.rewritten_queries?.length > 0) {
              appendThinkingLine(`问题重写/拆分结果：${workflow.rewritten_queries.join("；")}。`);
            }
            if (workflow.intent) {
              const confidence =
                workflow.intent_confidence !== undefined ? `，置信度 ${workflow.intent_confidence.toFixed(2)}` : "";
              appendThinkingLine(`意图识别为 ${workflow.intent}${confidence}。`);
            }
          },
          onSources: async (sources) => {
            state.latestSources = sources;
            state.streamStage = sources.length > 0 ? "organizing" : "answering";
            appendThinkingLine(
              sources.length > 0 ? `知识库检索命中 ${sources.length} 个可引用片段。` : "知识库没有命中可直接引用的片段。"
            );
          },
          onMcpCalls: async (mcpCalls) => {
            state.latestMcpCalls = mcpCalls;
            if (mcpCalls.length > 0 && !state.latestSources.length) {
              state.streamStage = "organizing";
            }
            if (mcpCalls.length > 0) {
              appendThinkingLine(`调用 ${mcpCalls.length} 个 MCP 工具补充外部信息。`);
            }
          },
          onDelta: async (delta) => {
            await renderStreamSegments(delta);
          },
          onCancel: async () => {
            assistantMessage.state = "stopped";
            assistantMessage.content = assistantMessage.content || "已停止生成。";
            state.messages = [...state.messages];
            await nextTick();
          },
          onFinal: async (payload) => {
            appendThinkingLine("正在整理上下文并生成最终回答。");
            await finishThinking();
            if (payload?.mode === "append" && payload.content_delta) {
              await renderStreamSegments(payload.content_delta);
            } else if (payload?.mode === "replace" && typeof payload.content === "string") {
              const currentNormalized = normalizeForFinalComparison(assistantMessage.content);
              const finalNormalized = normalizeForFinalComparison(payload.content);
              const finalContainsCurrent = currentNormalized.length > 0 && finalNormalized.includes(currentNormalized);
              if (!finalContainsCurrent) {
                assistantMessage.content = payload.content;
              }
              state.messages = [...state.messages];
            }
            assistantMessage.state = "complete";
            state.messages = [...state.messages];
            await nextTick();
          },
          onDone: async () => {
            await finishThinking();
            assistantMessage.state = "complete";
            const sessionMessages = await fetchSessionMessages(streamSessionId);
            const latestAssistantMessage = [...sessionMessages.items].reverse().find((item) => item.role === "assistant");
            if (latestAssistantMessage) {
              assistantMessage.backendId = latestAssistantMessage.id;
            }
            state.messages = [...state.messages];
            await nextTick();
            await loadSessions();
          }
        },
        controller.signal,
        Boolean(options.deepThinking),
        Boolean(options.smartSearch)
      );
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        state.infoMessage = "已停止本次生成。";
        state.streamStage = "idle";
        const latestMessage = state.messages[state.messages.length - 1];
        if (latestMessage?.role === "assistant" && latestMessage.state === "streaming") {
          latestMessage.state = "stopped";
          latestMessage.content = latestMessage.content || "已停止生成。";
          state.messages = [...state.messages];
        }
        return;
      }

      const message = error instanceof Error ? error.message : "聊天请求失败，请稍后再试。";
      state.errorMessage = message;
      state.streamStage = "idle";

      const latestMessage = state.messages[state.messages.length - 1];
      if (latestMessage?.role === "assistant" && latestMessage.state === "streaming") {
        latestMessage.state = "error";
        latestMessage.content = latestMessage.content || `这次流式回答失败了：${message}`;
        state.messages = [...state.messages];
      } else {
        state.messages = [...state.messages, buildMessage("assistant", `这次回答失败了：${message}`, "error")];
      }
    } finally {
      state.activeStreamController = null;
      state.activeStreamTaskId = "";
      state.loading = false;
      state.requestPhase = "idle";
      if (state.streamStage !== "stopping") {
        state.streamStage = "idle";
      }
    }
  };

  const stopStreaming = () => {
    const state = activeState.value;
    if (!state.activeStreamController) {
      return;
    }
    state.requestPhase = "stopping";
    state.streamStage = "stopping";
    const controller = state.activeStreamController;
    const taskId = state.activeStreamTaskId;
    if (!taskId) {
      controller.abort();
      return;
    }
    void cancelChatStreamTask(taskId).finally(() => {
      controller.abort();
    });
  };

  const retryLastQuestion = async () => {
    const state = activeState.value;
    if (!state.lastSubmittedQuestion.trim()) {
      return;
    }
    await ask(state.lastSubmittedQuestion, {
      deepThinking: state.lastSubmittedDeepThinking,
      smartSearch: state.lastSubmittedSmartSearch
    });
  };

  const submitFeedback = async (message: ChatMessage, vote: 1 | -1) => {
    if (message.role !== "assistant" || !message.backendId || message.state !== "complete") {
      return;
    }
    const state = activeState.value;
    message.feedbackState = "saving";
    state.messages = [...state.messages];
    try {
      await submitMessageFeedback(message.backendId, vote);
      message.feedbackVote = vote;
      message.feedbackState = "saved";
    } catch (error) {
      message.feedbackState = "error";
      state.errorMessage = error instanceof Error ? error.message : "反馈提交失败";
    } finally {
      state.messages = [...state.messages];
    }
  };

  return {
    activeSessionId,
    ask,
    canStop,
    canRetry,
    createNewSession,
    errorMessage,
    hasMessages,
    latestMcpCalls,
    latestSources,
    latestWorkflow,
    loadStarterPrompts,
    loadMessages,
    loadSessions,
    loading,
    messages,
    requestPhase,
    removeSession,
    renameSession,
    retryLastQuestion,
    selectSession,
    sessions,
    starterPrompts,
    statusText,
    stopStreaming,
    submitFeedback
  };
}
