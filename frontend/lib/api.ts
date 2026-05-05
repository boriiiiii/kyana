import type { Stats, Conversation, Message } from "./types";

const BASE = "/api";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchStats(): Promise<Stats> {
  return apiFetch<Stats>("/stats");
}

export async function fetchConversations(
  skip = 0,
  limit = 100
): Promise<Conversation[]> {
  return apiFetch<Conversation[]>(
    `/conversations?skip=${skip}&limit=${limit}`
  );
}

export async function fetchMessages(conversationId: number): Promise<Message[]> {
  return apiFetch<Message[]>(`/conversations/${conversationId}/messages`);
}

export async function patchConversationMode(
  conversationId: number,
  mode: "auto" | "manual"
): Promise<Conversation> {
  return apiFetch<Conversation>(`/conversations/${conversationId}/mode`, {
    method: "PATCH",
    body: JSON.stringify({ mode }),
  });
}
