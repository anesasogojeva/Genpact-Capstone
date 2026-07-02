const MAX_CONVERSATIONS = 30;

function storageKey(userId) {
  return `deskdibs-ai-chats-${userId ?? 'guest'}`;
}

function createConversation(title = 'New conversation') {
  const now = Date.now();
  return {
    id: crypto.randomUUID(),
    title,
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
}

export function loadChatState(userId) {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) {
      const conversation = createConversation();
      return {
        activeConversationId: conversation.id,
        conversations: [conversation],
      };
    }
    const parsed = JSON.parse(raw);
    if (!parsed?.conversations?.length) {
      const conversation = createConversation();
      return {
        activeConversationId: conversation.id,
        conversations: [conversation],
      };
    }
    const activeConversationId =
      parsed.activeConversationId &&
      parsed.conversations.some((item) => item.id === parsed.activeConversationId)
        ? parsed.activeConversationId
        : parsed.conversations[0].id;
    return { activeConversationId, conversations: parsed.conversations };
  } catch {
    const conversation = createConversation();
    return {
      activeConversationId: conversation.id,
      conversations: [conversation],
    };
  }
}

export function saveChatState(userId, state) {
  const conversations = [...state.conversations]
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, MAX_CONVERSATIONS);

  const activeConversationId = conversations.some(
    (item) => item.id === state.activeConversationId,
  )
    ? state.activeConversationId
    : conversations[0]?.id;

  const nextState = { activeConversationId, conversations };
  localStorage.setItem(storageKey(userId), JSON.stringify(nextState));
  return nextState;
}

export function startNewConversation(userId, state) {
  const conversation = createConversation();
  return saveChatState(userId, {
    activeConversationId: conversation.id,
    conversations: [conversation, ...state.conversations],
  });
}

export function deleteConversation(userId, state, conversationId) {
  const conversations = state.conversations.filter((item) => item.id !== conversationId);
  if (conversations.length === 0) {
    const conversation = createConversation();
    return saveChatState(userId, {
      activeConversationId: conversation.id,
      conversations: [conversation],
    });
  }
  const activeConversationId =
    state.activeConversationId === conversationId
      ? conversations[0].id
      : state.activeConversationId;
  return saveChatState(userId, { activeConversationId, conversations });
}

export function updateConversationMessages(userId, state, conversationId, messages, title) {
  const now = Date.now();
  const conversations = state.conversations.map((item) => {
    if (item.id !== conversationId) return item;
    return {
      ...item,
      messages,
      title: title ?? item.title,
      updatedAt: now,
    };
  });
  return saveChatState(userId, {
    activeConversationId: state.activeConversationId,
    conversations,
  });
}

export function deriveConversationTitle(firstUserMessage) {
  const trimmed = firstUserMessage.trim();
  if (!trimmed) return 'New conversation';
  return trimmed.length > 42 ? `${trimmed.slice(0, 42)}…` : trimmed;
}

export function formatConversationDate(timestamp) {
  return new Date(timestamp).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}
