import { computed, nextTick, ref, shallowRef } from "vue";

import {
  cancelChatStreamTask,
  createSession,
  deleteSession,
  fetchKnowledgeBases,
  fetchRouteProfile,
  fetchSessionMessages,
  fetchSessions,
  streamChatMessage,
  submitMessageFeedback,
  updateSession,
  type ChatMcpCallItem,
  type ChatSourceItem,
  type ChatWorkflow
} from "../services/api";

export interface ChatMessage {
  id: string;
  backendId?: number;
  role: "assistant" | "user";
  content: string;
  state: "complete" | "error" | "stopped" | "streaming";
  feedbackVote?: 1 | -1;
  feedbackState?: "idle" | "saving" | "saved" | "error";
}

type RequestPhase = "idle" | "retrieving" | "stopping" | "streaming";
type StreamStage = "idle" | "analyzing" | "retrieving" | "organizing" | "answering" | "stopping";

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

function normalizeForFinalComparison(value: string): string {
  return value.replace(/\s+/g, "").trim();
}

export function useRetriFlowChat() {
  const loading = shallowRef(false);
  const requestPhase = shallowRef<RequestPhase>("idle");
  const streamStage = shallowRef<StreamStage>("idle");
  const errorMessage = shallowRef("");
  const infoMessage = shallowRef("");
  const lastSubmittedQuestion = shallowRef("");
  const lastSubmittedDeepThinking = shallowRef(false);
  const activeStreamController = shallowRef<AbortController | null>(null);
  const activeStreamTaskId = shallowRef("");
  const sessions = ref<Awaited<ReturnType<typeof fetchSessions>>["items"]>([]);
  const activeSessionId = shallowRef("");
  const messages = ref<ChatMessage[]>([]);
  const latestSources = ref<ChatSourceItem[]>([]);
  const latestWorkflow = ref<ChatWorkflow | null>(null);
  const latestMcpCalls = ref<ChatMcpCallItem[]>([]);
  const starterPrompts = ref<string[]>([
    "RetriFlow 一期应该先做什么？",
    "这个知识库主要覆盖什么内容？",
    "帮我总结一下当前项目的 RAG 流程。"
  ]);

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
    messages.value = data.items.map((item) => buildMessage(item.role, item.content, "complete", item.id));
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
    if (loading.value && activeStreamController.value) {
      infoMessage.value = "当前回答还在生成，已保留当前会话。";
      return;
    }

    const previousActiveSessionId = activeSessionId.value;
    const previousMessages = messages.value;
    latestSources.value = [];
    latestWorkflow.value = null;
    latestMcpCalls.value = [];
    errorMessage.value = "";
    infoMessage.value = "正在创建新会话...";
    requestPhase.value = "idle";
    streamStage.value = "idle";
    messages.value = [];

    try {
      const created = await createSession(`RetriFlow 新会话 ${sessions.value.length + 1}`);
      activeSessionId.value = created.id;
      sessions.value = [created, ...sessions.value.filter((session) => session.id !== created.id)];
      await loadSessions();
      activeSessionId.value = created.id;
      infoMessage.value = "新会话已创建，可以直接开始提问。";
    } catch (error) {
      activeSessionId.value = previousActiveSessionId;
      messages.value = previousMessages;
      infoMessage.value = "";
      errorMessage.value = error instanceof Error ? error.message : "新建会话失败，请稍后再试。";
    }
  };
  const removeSession = async (sessionId: string) => {
    const wasActiveSession = activeSessionId.value === sessionId;
    const previousSessions = sessions.value;
    sessions.value = sessions.value.filter((session) => session.id !== sessionId);
    try {
      await deleteSession(sessionId);
      if (wasActiveSession) {
        latestSources.value = [];
        latestWorkflow.value = null;
        latestMcpCalls.value = [];
        errorMessage.value = "";
        infoMessage.value = "??????";
        messages.value = [];
      }
      await loadSessions();
      if (wasActiveSession) {
        await loadMessages(activeSessionId.value);
      }
    } catch (error) {
      sessions.value = previousSessions;
      errorMessage.value = error instanceof Error ? error.message : "?????????????";
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
      const knowledgeBaseData = await fetchKnowledgeBases();
      const profiles = await Promise.all(
        knowledgeBaseData.items.slice(0, 8).map((item) => fetchRouteProfile(item.id))
      );
      const configuredPrompts = profiles
        .flatMap((profile) => profile.sample_questions)
        .map((prompt) => prompt.trim())
        .filter(Boolean);
      starterPrompts.value = Array.from(new Set(configuredPrompts)).slice(0, 6);
      if (starterPrompts.value.length === 0) {
        starterPrompts.value = [
          "RetriFlow 一期应该先做什么？",
          "这个知识库主要覆盖什么内容？",
          "帮我总结一下当前项目的 RAG 流程。"
        ];
      }
    } catch {
      starterPrompts.value = [
        "RetriFlow 一期应该先做什么？",
        "这个知识库主要覆盖什么内容？",
        "帮我总结一下当前项目的 RAG 流程。"
      ];
    }
  };

  const ask = async (question: string, options: { deepThinking?: boolean } = {}) => {
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
    lastSubmittedDeepThinking.value = Boolean(options.deepThinking);
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
          onTask: async (payload) => {
            activeStreamTaskId.value = payload.task_id;
          },
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
          onCancel: async () => {
            assistantMessage.state = "stopped";
            assistantMessage.content = assistantMessage.content || "已停止生成。";
            messages.value = [...messages.value];
            await nextTick();
          },
          onFinal: async (payload) => {
            if (payload?.mode === "append" && payload.content_delta) {
              await renderStreamSegments(payload.content_delta);
            } else if (payload?.mode === "replace" && typeof payload.content === "string") {
              const currentNormalized = normalizeForFinalComparison(assistantMessage.content);
              const finalNormalized = normalizeForFinalComparison(payload.content);
              const finalContainsCurrent = currentNormalized.length > 0 && finalNormalized.includes(currentNormalized);
              if (!finalContainsCurrent) {
                assistantMessage.content = payload.content;
              }
              messages.value = [...messages.value];
            }
            assistantMessage.state = "complete";
            messages.value = [...messages.value];
            await nextTick();
          },
          onDone: async () => {
            assistantMessage.state = "complete";
            const sessionMessages = await fetchSessionMessages(activeSessionId.value);
            const latestAssistantMessage = [...sessionMessages.items].reverse().find((item) => item.role === "assistant");
            if (latestAssistantMessage) {
              assistantMessage.backendId = latestAssistantMessage.id;
            }
            messages.value = [...messages.value];
            await nextTick();
            await loadSessions();
          }
        },
        controller.signal,
        Boolean(options.deepThinking)
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
      activeStreamTaskId.value = "";
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
    const controller = activeStreamController.value;
    const taskId = activeStreamTaskId.value;
    if (!taskId) {
      controller.abort();
      return;
    }
    void cancelChatStreamTask(taskId).finally(() => {
      controller.abort();
    });
  };

  const retryLastQuestion = async () => {
    if (!lastSubmittedQuestion.value.trim()) {
      return;
    }
    await ask(lastSubmittedQuestion.value, { deepThinking: lastSubmittedDeepThinking.value });
  };

  const submitFeedback = async (message: ChatMessage, vote: 1 | -1) => {
    if (message.role !== "assistant" || !message.backendId || message.state !== "complete") {
      return;
    }
    message.feedbackState = "saving";
    messages.value = [...messages.value];
    try {
      await submitMessageFeedback(message.backendId, vote);
      message.feedbackVote = vote;
      message.feedbackState = "saved";
    } catch (error) {
      message.feedbackState = "error";
      errorMessage.value = error instanceof Error ? error.message : "反馈提交失败";
    } finally {
      messages.value = [...messages.value];
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
