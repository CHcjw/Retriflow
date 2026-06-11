import { computed, nextTick, ref, shallowRef } from "vue";

import {
  createSession,
  deleteSession,
  fetchSessionMessages,
  fetchSessions,
  streamChatMessage,
  type ChatMcpCallItem,
  type ChatSourceItem,
  type ChatWorkflow
} from "../services/api";

export interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  state: "complete" | "error" | "stopped" | "streaming";
}

type RequestPhase = "idle" | "retrieving" | "stopping" | "streaming";
type StreamStage = "idle" | "analyzing" | "retrieving" | "organizing" | "answering" | "stopping";

function buildMessage(
  role: ChatMessage["role"],
  content: string,
  state: ChatMessage["state"] = "complete"
): ChatMessage {
  return {
    id: `${role}-${crypto.randomUUID()}`,
    role,
    content,
    state
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

    if (/[。！？!?]/.test(current)) {
      segments.push(buffer);
      buffer = "";
      continue;
    }

    if (/[，、；：;:]/.test(current) && buffer.trim().length >= 8) {
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
  if (/[。！？!?]$/.test(value)) {
    return 96;
  }
  if (/[；：;:]$/.test(value)) {
    return 74;
  }
  if (/[，、]$/.test(value)) {
    return 48;
  }
  return Math.min(38, 14 + value.length * 2);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export function useRetriFlowChat() {
  const loading = shallowRef(false);
  const requestPhase = shallowRef<RequestPhase>("idle");
  const streamStage = shallowRef<StreamStage>("idle");
  const errorMessage = shallowRef("");
  const infoMessage = shallowRef("");
  const lastSubmittedQuestion = shallowRef("");
  const activeStreamController = shallowRef<AbortController | null>(null);
  const sessions = ref<Awaited<ReturnType<typeof fetchSessions>>["items"]>([]);
  const activeSessionId = shallowRef("");
  const messages = ref<ChatMessage[]>([]);
  const latestSources = ref<ChatSourceItem[]>([]);
  const latestWorkflow = ref<ChatWorkflow | null>(null);
  const latestMcpCalls = ref<ChatMcpCallItem[]>([]);

  const statusText = computed(() => {
    if (requestPhase.value === "stopping" || streamStage.value === "stopping") {
      return "正在停止本次回答...";
    }
    if (loading.value) {
      if (streamStage.value === "analyzing") {
        return "正在理解你的问题...";
      }
      if (streamStage.value === "retrieving") {
        return "正在检索相关资料...";
      }
      if (streamStage.value === "organizing") {
        return "正在整理参考内容...";
      }
      if (streamStage.value === "answering") {
        return "正在生成回答...";
      }
      return "正在准备回答...";
    }
    if (errorMessage.value) {
      return errorMessage.value;
    }
    if (infoMessage.value) {
      return infoMessage.value;
    }
    return "";
  });

  const hasMessages = computed(() => messages.value.length > 0);
  const canRetry = computed(() => Boolean(lastSubmittedQuestion.value.trim()) && !loading.value);
  const canStop = computed(() => loading.value && activeStreamController.value !== null);

  const loadSessions = async () => {
    const data = await fetchSessions();
    sessions.value = data.items;
    if (!sessions.value.find((item) => item.id === activeSessionId.value) && sessions.value[0]) {
      activeSessionId.value = sessions.value[0].id;
    }
    if (!sessions.value[0]) {
      activeSessionId.value = "";
    }
  };

  const loadMessages = async (sessionId = activeSessionId.value) => {
    if (!sessionId) {
      messages.value = [];
      return;
    }
    const data = await fetchSessionMessages(sessionId);
    messages.value = data.items.map((item) => buildMessage(item.role, item.content));
  };

  const selectSession = async (sessionId: string) => {
    activeSessionId.value = sessionId;
    latestSources.value = [];
    latestWorkflow.value = null;
    latestMcpCalls.value = [];
    errorMessage.value = "";
    infoMessage.value = "";
    requestPhase.value = "idle";
    streamStage.value = "idle";
    await loadMessages(sessionId);
  };

  const createNewSession = async () => {
    const created = await createSession(`RetriFlow 新会话 ${sessions.value.length + 1}`);
    await loadSessions();
    activeSessionId.value = created.id;
    latestSources.value = [];
    latestWorkflow.value = null;
    latestMcpCalls.value = [];
    errorMessage.value = "";
    infoMessage.value = "新会话已创建，可以直接开始提问。";
    requestPhase.value = "idle";
    streamStage.value = "idle";
    messages.value = [];
  };

  const removeSession = async (sessionId: string) => {
    await deleteSession(sessionId);
    if (activeSessionId.value === sessionId) {
      latestSources.value = [];
      latestWorkflow.value = null;
      latestMcpCalls.value = [];
      errorMessage.value = "";
      infoMessage.value = "会话已删除。";
    }
    await loadSessions();
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = sessions.value[0]?.id ?? "";
      await loadMessages(activeSessionId.value);
    }
  };

  const ask = async (question: string) => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      return;
    }

    if (!activeSessionId.value) {
      await createNewSession();
    }

    loading.value = true;
    requestPhase.value = "retrieving";
    streamStage.value = "analyzing";
    errorMessage.value = "";
    infoMessage.value = "";
    lastSubmittedQuestion.value = trimmedQuestion;
    latestSources.value = [];
    latestWorkflow.value = null;
    latestMcpCalls.value = [];
    messages.value = [...messages.value, buildMessage("user", trimmedQuestion)];

    try {
      const assistantMessage = buildMessage("assistant", "", "streaming");
      const controller = new AbortController();
      activeStreamController.value = controller;
      messages.value = [...messages.value, assistantMessage];

      let hasStreamedVisibleText = false;

      const renderStreamSegments = async (content: string) => {
        const segments = splitStreamingSegments(content);
        if (segments.length === 0) {
          return;
        }

        requestPhase.value = "streaming";
        streamStage.value = "answering";
        assistantMessage.state = "streaming";

        if (!hasStreamedVisibleText) {
          hasStreamedVisibleText = true;
          await sleep(72);
        }

        for (const [index, segment] of segments.entries()) {
          assistantMessage.content = `${assistantMessage.content}${segment}`;
          messages.value = [...messages.value];
          await nextTick();
          await sleep(getSegmentDelay(segment, index));
        }
      };

      await streamChatMessage(
        activeSessionId.value,
        trimmedQuestion,
        {
          onWorkflow: async (workflow) => {
            latestWorkflow.value = workflow;
            if (streamStage.value === "analyzing") {
              streamStage.value = workflow.retrieval_count > 0 ? "retrieving" : "organizing";
            }
          },
          onSources: async (sources) => {
            latestSources.value = sources;
            streamStage.value = sources.length > 0 ? "organizing" : "answering";
          },
          onMcpCalls: async (mcpCalls) => {
            latestMcpCalls.value = mcpCalls;
            if (mcpCalls.length > 0 && !latestSources.value.length) {
              streamStage.value = "organizing";
            }
          },
          onDelta: async (delta) => {
            await renderStreamSegments(delta);
          },
          onFinal: async (payload) => {
            if (payload?.mode === "append" && payload.content_delta) {
              await renderStreamSegments(payload.content_delta);
            } else if (payload?.mode === "replace" && typeof payload.content === "string") {
              assistantMessage.content = payload.content;
              messages.value = [...messages.value];
            }
            assistantMessage.state = "complete";
            messages.value = [...messages.value];
            await nextTick();
          },
          onDone: async () => {
            assistantMessage.state = "complete";
            messages.value = [...messages.value];
            await nextTick();
            await loadSessions();
          }
        },
        controller.signal
      );
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        infoMessage.value = "已停止本次生成。";
        streamStage.value = "idle";
        const latestMessage = messages.value[messages.value.length - 1];
        if (latestMessage?.role === "assistant" && latestMessage.state === "streaming") {
          latestMessage.state = "stopped";
          latestMessage.content = latestMessage.content || "已停止生成。";
          messages.value = [...messages.value];
        }
        return;
      }

      const message = error instanceof Error ? error.message : "聊天请求失败，请稍后再试。";
      errorMessage.value = message;
      streamStage.value = "idle";

      const latestMessage = messages.value[messages.value.length - 1];
      if (latestMessage?.role === "assistant" && latestMessage.state === "streaming") {
        latestMessage.state = "error";
        latestMessage.content = latestMessage.content || `这次流式回答失败了：${message}`;
        messages.value = [...messages.value];
      } else {
        messages.value = [...messages.value, buildMessage("assistant", `这次回答失败了：${message}`, "error")];
      }
    } finally {
      activeStreamController.value = null;
      loading.value = false;
      requestPhase.value = "idle";
      if (streamStage.value !== "stopping") {
        streamStage.value = "idle";
      }
    }
  };

  const stopStreaming = () => {
    if (!activeStreamController.value) {
      return;
    }
    requestPhase.value = "stopping";
    streamStage.value = "stopping";
    activeStreamController.value.abort();
  };

  const retryLastQuestion = async () => {
    if (!lastSubmittedQuestion.value.trim()) {
      return;
    }
    await ask(lastSubmittedQuestion.value);
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
    loadMessages,
    loadSessions,
    loading,
    messages,
    requestPhase,
    removeSession,
    retryLastQuestion,
    selectSession,
    sessions,
    statusText,
    stopStreaming
  };
}
