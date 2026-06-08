import { computed, ref, shallowRef } from "vue";

import {
  createSession,
  fetchSessionMessages,
  fetchSessions,
  sendChatMessage,
  streamChatMessage,
  type ChatSourceItem,
  type ChatWorkflow
} from "../services/api";

export interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  state: "complete" | "error" | "stopped" | "streaming";
}

const DEFAULT_SESSION_ID = "session-demo-1";

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

function createEmptySessionMessage(): ChatMessage {
  return buildMessage("assistant", "当前会话还没有消息，可以先提一个问题试试。");
}

export function useRetriFlowChat() {
  const loading = shallowRef(false);
  const streamMode = shallowRef(true);
  const requestPhase = shallowRef<"idle" | "retrieving" | "stopping" | "streaming">("idle");
  const errorMessage = shallowRef("");
  const infoMessage = shallowRef("");
  const lastSubmittedQuestion = shallowRef("");
  const activeStreamController = shallowRef<AbortController | null>(null);
  const sessions = ref<Awaited<ReturnType<typeof fetchSessions>>["items"]>([]);
  const activeSessionId = shallowRef(DEFAULT_SESSION_ID);
  const messages = ref<ChatMessage[]>([
    buildMessage("assistant", "RetriFlow 聊天页面已接入后端接口，现在支持来源展示、工作流元数据和实时流式回复。")
  ]);
  const latestSources = ref<ChatSourceItem[]>([]);
  const latestWorkflow = ref<ChatWorkflow | null>(null);

  const statusText = computed(() => {
    if (requestPhase.value === "retrieving") {
      return streamMode.value ? "正在检索知识并连接模型..." : "正在生成回答...";
    }
    if (requestPhase.value === "streaming") {
      return "模型正在流式输出...";
    }
    if (requestPhase.value === "stopping") {
      return "正在停止本次生成...";
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
  const canStop = computed(() => loading.value && streamMode.value && activeStreamController.value !== null);

  const loadSessions = async () => {
    const data = await fetchSessions();
    sessions.value = data.items;
    if (!sessions.value.find((item) => item.id === activeSessionId.value) && sessions.value[0]) {
      activeSessionId.value = sessions.value[0].id;
    }
  };

  const loadMessages = async (sessionId = activeSessionId.value) => {
    const data = await fetchSessionMessages(sessionId);
    messages.value =
      data.items.length > 0
        ? data.items.map((item) => buildMessage(item.role, item.content))
        : [createEmptySessionMessage()];
  };

  const selectSession = async (sessionId: string) => {
    activeSessionId.value = sessionId;
    latestSources.value = [];
    latestWorkflow.value = null;
    errorMessage.value = "";
    infoMessage.value = "";
    requestPhase.value = "idle";
    await loadMessages(sessionId);
  };

  const createNewSession = async () => {
    const created = await createSession(`RetriFlow 新会话 ${sessions.value.length + 1}`);
    await loadSessions();
    activeSessionId.value = created.id;
    latestSources.value = [];
    latestWorkflow.value = null;
    errorMessage.value = "";
    infoMessage.value = "";
    requestPhase.value = "idle";
    messages.value = [buildMessage("assistant", "新的 RetriFlow 会话已经创建，可以继续提问。")];
  };

  const ask = async (question: string) => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      return;
    }

    loading.value = true;
    requestPhase.value = "retrieving";
    errorMessage.value = "";
    infoMessage.value = "";
    lastSubmittedQuestion.value = trimmedQuestion;
    latestSources.value = [];
    latestWorkflow.value = null;
    messages.value = [...messages.value, buildMessage("user", trimmedQuestion)];

    try {
      if (streamMode.value) {
        const assistantMessage = buildMessage("assistant", "", "streaming");
        const controller = new AbortController();
        activeStreamController.value = controller;
        messages.value = [...messages.value, assistantMessage];

        await streamChatMessage(
          activeSessionId.value,
          trimmedQuestion,
          {
            onWorkflow: (workflow) => {
              latestWorkflow.value = workflow;
            },
            onSources: (sources) => {
              latestSources.value = sources;
            },
            onDelta: (delta) => {
              requestPhase.value = "streaming";
              assistantMessage.content = `${assistantMessage.content}${delta}`;
              messages.value = [...messages.value];
            },
            onFinal: (content) => {
              assistantMessage.content = content;
              assistantMessage.state = "complete";
              messages.value = [...messages.value];
            },
            onDone: async () => {
              assistantMessage.state = "complete";
              messages.value = [...messages.value];
              await loadSessions();
            }
          },
          controller.signal
        );
      } else {
        const response = await sendChatMessage(activeSessionId.value, trimmedQuestion);
        latestSources.value = response.sources;
        latestWorkflow.value = response.workflow;
        messages.value = [...messages.value, buildMessage("assistant", response.assistant_message)];
        await loadSessions();
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        infoMessage.value = "已停止本次生成。";
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
    }
  };

  const stopStreaming = () => {
    if (!activeStreamController.value) {
      return;
    }
    requestPhase.value = "stopping";
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
    latestSources,
    latestWorkflow,
    loadMessages,
    loadSessions,
    loading,
    messages,
    requestPhase,
    retryLastQuestion,
    selectSession,
    sessions,
    stopStreaming,
    statusText,
    streamMode
  };
}
