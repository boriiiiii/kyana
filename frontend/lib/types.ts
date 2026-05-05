export interface Stats {
  total_conversations: number;
  auto_conversations: number;
  manual_conversations: number;
  total_messages: number;
  needs_human_count: number;
}

export interface Conversation {
  id: number;
  sender_id: string;
  mode: "auto" | "manual";
  last_message_at: string;
  created_at: string;
  last_message_preview: string | null;
  needs_human?: boolean;
}

export interface Message {
  id: number;
  conversation_id: number;
  direction: "inbound" | "outbound";
  content: string;
  needs_human: boolean;
  created_at: string;
}
