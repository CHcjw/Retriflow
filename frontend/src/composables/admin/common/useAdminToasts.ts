import { onBeforeUnmount, shallowRef } from "vue";

export type AdminToastTone = "success" | "info" | "danger";

export type AdminToastItem = {
  id: number;
  message: string;
  tone: AdminToastTone;
};

export function useAdminToasts() {
  const toasts = shallowRef<AdminToastItem[]>([]);
  const timers = new Map<number, ReturnType<typeof window.setTimeout>>();
  let nextToastId = 1;

  function dismissToast(id: number) {
    const timer = timers.get(id);
    if (timer) {
      window.clearTimeout(timer);
      timers.delete(id);
    }
    toasts.value = toasts.value.filter((toast) => toast.id !== id);
  }

  function pushToast(message: string, tone: AdminToastTone = "success") {
    const trimmedMessage = message.trim();
    if (!trimmedMessage) {
      return;
    }

    const id = nextToastId;
    nextToastId += 1;
    toasts.value = [...toasts.value, { id, message: trimmedMessage, tone }];
    timers.set(
      id,
      window.setTimeout(() => {
        dismissToast(id);
      }, 4000)
    );
  }

  onBeforeUnmount(() => {
    timers.forEach((timer) => window.clearTimeout(timer));
    timers.clear();
  });

  return {
    toasts,
    pushToast,
    dismissToast
  };
}
