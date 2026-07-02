import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { format, parseISO } from 'date-fns';
import {
  Bot,
  Building2,
  CalendarCheck,
  Loader2,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  Send,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { toast } from 'react-toastify';
import { sendAiChat, getTeamMembers } from '../api/client';
import {
  deleteConversation,
  deriveConversationTitle,
  formatConversationDate,
  loadChatState,
  saveChatState,
  startNewConversation,
  updateConversationMessages,
} from '../lib/aiChatStorage';
import PageHeader from '../components/ui/PageHeader';
import { useAuth } from '../context/AuthContext';

const DESK_PROMPTS = [
  'Book a desk for tomorrow',
  'Search desks for tomorrow',
  'Cancel my reservation for tomorrow',
];

const ROOM_PROMPTS = [
  'Book a meeting room for 6 people tomorrow at 2 PM',
  'Search meeting rooms for 6 people tomorrow',
];

const FALLBACK_COLLEAGUE_NAMES = ['Alex', 'Jane', 'Sarah', 'Priya'];

function firstName(fullName) {
  return fullName?.trim().split(/\s+/)[0] || null;
}

function buildColleaguePrompts(user, teammates = []) {
  const selfFirst = firstName(user?.full_name)?.toLowerCase();
  const teammateNames = teammates
    .map((member) => firstName(member.full_name))
    .filter((name) => name && name.toLowerCase() !== selfFirst);
  const fallbackNames = FALLBACK_COLLEAGUE_NAMES.filter(
    (name) => name.toLowerCase() !== selfFirst,
  );
  const primary = teammateNames[0] ?? fallbackNames[0] ?? 'my colleague';
  const secondary =
    teammateNames.find((name) => name !== primary)
    ?? fallbackNames.find((name) => name !== primary)
    ?? 'Sarah';

  return [
    `Where is ${primary} sitting tomorrow?`,
    'Tell me where my colleagues are sitting on Friday',
    `Is ${secondary} in the office tomorrow?`,
    `When is ${secondary} in the office?`,
  ];
}

function canBookRooms(role) {
  return role === 'team_leader' || role === 'manager';
}

function buildAssistantText(response) {
  if (response.confirmation) return response.confirmation;
  if (response.follow_up_question) return response.follow_up_question;

  if (response.action === 'cancel_reservation_not_found') {
    const dateLabel = response.reservation_date || response.date;
    return dateLabel
      ? `You don't have any reservations for ${dateLabel}.`
      : "You don't have any upcoming reservations to cancel.";
  }

  if (response.action === 'cancelled_reservation') {
    return response.confirmation || `Reservation #${response.reservation_id} was cancelled.`;
  }

  if (response.colleagues?.length) {
    return response.confirmation || 'Colleague desk information is ready.';
  }

  if (response.action === 'find_colleague_empty') {
    return response.confirmation || 'No upcoming desk reservations were found for that colleague.';
  }

  if (
    response.action === 'book_desk_no_preference_match'
    || response.action === 'search_desks_no_preference_match'
  ) {
    return response.confirmation || 'No desk matches those preferences for that date.';
  }

  if (response.action === 'find_colleague_needs_info') {
    return response.confirmation || response.follow_up_question || 'I need more details to find your colleague.';
  }

  if (response.resources?.length) {
    const names = response.resources.map((resource) => resource.name).join(', ');
    return `Found ${response.resources.length} available option(s): ${names}.`;
  }

  const actionText = {
    book_meeting_room_no_availability: 'No meeting room matches those requirements for that date.',
    book_meeting_room_failed: response.follow_up_question || 'The meeting room could not be booked.',
    book_desk_no_availability: response.confirmation || 'No desks are available for that date.',
    book_desk_colleague_not_in_office:
      response.confirmation || 'That colleague is not in the office on that date.',
    book_desk_no_near_colleague:
      response.confirmation || 'No desks are available near that colleague on that date.',
    book_desk_failed: response.follow_up_question || 'The desk could not be booked.',
    search_meeting_rooms_empty: 'No meeting rooms are available for that date.',
    search_desks_empty: 'No desks are available for that date.',
    cancel_reservation_failed: 'The reservation could not be cancelled.',
  };

  if (response.action && actionText[response.action]) {
    return actionText[response.action];
  }

  return 'Request processed.';
}

function isSuccessAction(action) {
  return ['booked_meeting_room', 'booked_desk', 'cancelled_reservation'].includes(action);
}

function isColleagueAction(action) {
  return ['find_colleague', 'find_colleague_empty', 'find_colleague_needs_info'].includes(action);
}

function isInfoAction(action) {
  return (
    action === 'cancel_reservation_not_found'
    || action === 'book_desk_colleague_not_in_office'
    || action === 'book_desk_no_near_colleague'
    || action === 'book_desk_no_preference_match'
    || action === 'search_desks_no_preference_match'
    || action === 'desk_proximity_followup'
    || isColleagueAction(action)
  );
}

function isSearchAction(action) {
  return ['search_meeting_rooms', 'search_desks', 'desk_proximity_followup'].includes(action);
}

function formatHistory(messages) {
  return messages.map((message) => ({
    role: message.role,
    content:
      message.role === 'assistant' && message.response
        ? JSON.stringify(message.response)
        : message.content,
  }));
}

function ResponseDetails({ response }) {
  const rows = [
    ['Intent', response.intent],
    ['Action', response.action],
    ['Reservation ID', response.reservation_id],
    ['Reservation date', response.reservation_date],
    ['Room', response.room_name],
    ['Desk', response.desk_name],
    ['People', response.people],
    ['Date', response.date],
    ['Time', response.time],
    ['Coworker', response.coworker],
    ['Book for', response.book_for],
  ].filter(([, value]) => value !== null && value !== undefined && value !== '');

  if (rows.length === 0) return null;

  return (
    <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50/80">
      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-slate-600">
        View structured response
      </summary>
      <dl className="space-y-2 border-t border-slate-200 px-3 py-3 text-xs">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4">
            <dt className="text-slate-500">{label}</dt>
            <dd className="text-right font-medium text-slate-800">{String(value)}</dd>
          </div>
        ))}
        {response.equipment?.length > 0 && (
          <div className="flex justify-between gap-4">
            <dt className="text-slate-500">Equipment</dt>
            <dd className="text-right font-medium text-slate-800">{response.equipment.join(', ')}</dd>
          </div>
        )}
      </dl>
    </details>
  );
}

function ColleagueList({ colleagues }) {
  if (!colleagues?.length) return null;

  return (
    <div className="mt-3 space-y-2">
      {colleagues.map((colleague) => (
        <div
          key={`${colleague.name}-${colleague.date}`}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm"
        >
          <p className="font-medium text-slate-900">{colleague.name}</p>
          {colleague.in_office ? (
            <p className="text-xs text-slate-600">
              Desk {colleague.desk_name} · Floor {colleague.floor} · {colleague.zone} · {colleague.date}
            </p>
          ) : (
            <p className="text-xs text-slate-500">Not in the office on {colleague.date}</p>
          )}
        </div>
      ))}
    </div>
  );
}

function ResourceList({ resources }) {
  if (!resources?.length) return null;

  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      {resources.map((resource) => (
        <div
          key={resource.id}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm"
        >
          <p className="font-medium text-slate-900">{resource.name}</p>
          <p className="text-xs text-slate-500">
            Floor {resource.floor} · {resource.zone} · capacity {resource.capacity}
          </p>
        </div>
      ))}
    </div>
  );
}

function MessageBubble({ message }) {
  const isUser = message.role === 'user';
  const response = message.response;
  const success = response && isSuccessAction(response.action);
  const info = response && isInfoAction(response.action);

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[92%] rounded-2xl px-4 py-3 sm:max-w-[80%] ${
          isUser
            ? 'bg-brand-600 text-white'
            : success
              ? 'border border-emerald-200 bg-emerald-50 text-slate-900'
              : info
                ? 'border border-sky-200 bg-sky-50 text-slate-900'
                : 'border border-slate-200 bg-white text-slate-900'
        }`}
      >
        {!isUser && (
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <Bot size={14} />
            DeskDibs AI
          </div>
        )}
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>

        {!isUser && response && (
          <>
            {success && (response.room_name || response.desk_name) && (
              <div className="mt-3 rounded-lg border border-emerald-200 bg-white/80 px-3 py-2 text-xs text-slate-700">
                <p>
                  <span className="font-semibold">Resource:</span>{' '}
                  {response.room_name || response.desk_name}
                </p>
                <p>
                  <span className="font-semibold">Date:</span>{' '}
                  {response.reservation_date
                    ? format(parseISO(response.reservation_date), 'PPP')
                    : response.date}
                </p>
                {response.reservation_id && (
                  <p>
                    <span className="font-semibold">Reservation ID:</span> {response.reservation_id}
                  </p>
                )}
              </div>
            )}

            {((isSearchAction(response.action)
              || response.action === 'book_desk_no_preference_match'
              || response.action === 'search_desks_no_preference_match')
              && response.resources?.length > 0) && (
              <ResourceList resources={response.resources} />
            )}

            {response.colleagues?.length > 0 && (
              <ColleagueList colleagues={response.colleagues} />
            )}

            <ResponseDetails response={response} />
          </>
        )}
      </div>
    </div>
  );
}

export default function AiAssistant() {
  const { user } = useAuth();
  const userId = user?.id;
  const [chatState, setChatState] = useState(() => loadChatState(userId));
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [teammates, setTeammates] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(min-width: 1024px)').matches,
  );
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  const activeConversation = chatState.conversations.find(
    (item) => item.id === chatState.activeConversationId,
  );
  const messages = activeConversation?.messages ?? [];

  const suggestedPrompts = [
    ...DESK_PROMPTS,
    ...buildColleaguePrompts(user, teammates),
    ...(canBookRooms(user?.role) ? ROOM_PROMPTS : []),
  ];

  useEffect(() => {
    if (userId) {
      setChatState(loadChatState(userId));
    }
  }, [userId]);

  useEffect(() => {
    if (user?.role !== 'team_leader') {
      setTeammates([]);
      return undefined;
    }
    let cancelled = false;
    getTeamMembers()
      .then((members) => {
        if (!cancelled) setTeammates(members);
      })
      .catch(() => {
        if (!cancelled) setTeammates([]);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.id, user?.role]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading, chatState.activeConversationId]);

  const persistMessages = (conversationId, nextMessages, title) => {
    setChatState((current) =>
      updateConversationMessages(userId, current, conversationId, nextMessages, title),
    );
  };

  const handleNewChat = () => {
    setChatState((current) => startNewConversation(userId, current));
    setInput('');
    inputRef.current?.focus();
  };

  const handleSelectConversation = (conversationId) => {
    setChatState((current) =>
      saveChatState(userId, {
        ...current,
        activeConversationId: conversationId,
      }),
    );
  };

  const handleDeleteConversation = (event, conversationId) => {
    event.stopPropagation();
    setChatState((current) => deleteConversation(userId, current, conversationId));
  };

  const submitMessage = async (text) => {
    const trimmed = text.trim();
    if (!trimmed || loading || !activeConversation) return;

    const conversationId = activeConversation.id;
    const isFirstMessage = messages.length === 0;
    const title = isFirstMessage ? deriveConversationTitle(trimmed) : undefined;

    const userMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
    };

    const nextMessages = [...messages, userMessage];
    persistMessages(conversationId, nextMessages, title);
    setInput('');
    setLoading(true);

    try {
      const response = await sendAiChat(trimmed, formatHistory(messages));
      const assistantMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: buildAssistantText(response),
        response,
      };
      persistMessages(conversationId, [...nextMessages, assistantMessage]);

      if (isSuccessAction(response.action)) {
        toast.success('Reservation updated.');
      }
    } catch (error) {
      const detail = error?.response?.data?.detail;
      const errorText =
        typeof detail === 'string'
          ? detail
          : 'The AI assistant could not process that request.';

      persistMessages(conversationId, [
        ...nextMessages,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: errorText,
        },
      ]);
      toast.error(errorText);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    submitMessage(input);
  };

  const sortedConversations = [...chatState.conversations].sort(
    (a, b) => b.updatedAt - a.updatedAt,
  );

  return (
    <div className="mx-auto flex h-[calc(100vh-7.5rem)] max-w-7xl flex-col">
      <PageHeader
        title="AI Assistant"
        subtitle="Book desks, meeting rooms, search availability, or cancel reservations using natural language"
        action={
          <Link to="/reservations" className="btn-secondary">
            <CalendarCheck size={16} />
            My Reservations
          </Link>
        }
      />

      <div className="card flex min-h-0 flex-1 overflow-hidden">
        {sidebarOpen && (
          <aside className="flex w-72 shrink-0 flex-col border-r border-slate-200 bg-slate-50/80">
            <div className="border-b border-slate-200 p-3">
              <button
                type="button"
                onClick={handleNewChat}
                className="btn-primary w-full py-2.5"
              >
                <MessageSquarePlus size={16} />
                New chat
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
              <p className="px-2 py-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Previous chats
              </p>
              {sortedConversations.map((conversation) => {
                const isActive = conversation.id === chatState.activeConversationId;
                return (
                  <div
                    key={conversation.id}
                    className={`group mb-1 flex items-start gap-1 rounded-lg ${
                      isActive ? 'bg-brand-50 ring-1 ring-brand-200' : 'hover:bg-white'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => handleSelectConversation(conversation.id)}
                      className="min-w-0 flex-1 px-3 py-2.5 text-left"
                    >
                      <p className="truncate text-sm font-medium text-slate-900">
                        {conversation.title}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {formatConversationDate(conversation.updatedAt)}
                        {conversation.messages.length > 0 &&
                          ` · ${conversation.messages.length} messages`}
                      </p>
                    </button>
                    <button
                      type="button"
                      onClick={(event) => handleDeleteConversation(event, conversation.id)}
                      className="mr-2 mt-2 rounded-md p-1.5 text-slate-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover:opacity-100"
                      aria-label="Delete chat"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                );
              })}
            </div>

            <div className="border-t border-slate-200 px-3 py-2 text-[11px] text-slate-500">
              Saved on this device only
            </div>
          </aside>
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="border-b border-slate-100 bg-gradient-to-r from-brand-50 to-white px-4 py-4 sm:px-5">
            <div className="flex items-start gap-3">
              <button
                type="button"
                onClick={() => setSidebarOpen((open) => !open)}
                className="rounded-lg border border-slate-200 bg-white p-2 text-slate-600 hover:bg-slate-50"
                aria-label={sidebarOpen ? 'Hide chat history' : 'Show chat history'}
              >
                {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
              </button>
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-white">
                <Sparkles size={18} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-slate-900">
                  {activeConversation?.title ?? 'DeskDibs workspace assistant'}
                </p>
                <p className="text-sm text-slate-500">
                  Try prompts like booking a desk for tomorrow or searching available meeting rooms.
                  {!canBookRooms(user?.role) && (
                    <span className="block pt-1 text-amber-700">
                      Meeting room booking requires a team leader or manager account.
                    </span>
                  )}
                </p>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2 pl-11 sm:pl-14">
              {suggestedPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  disabled={loading}
                  onClick={() => submitMessage(prompt)}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-brand-300 hover:bg-brand-50 disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto bg-surface px-4 py-5 sm:px-6">
            {messages.length === 0 && !loading && (
              <div className="flex h-full min-h-[240px] flex-col items-center justify-center text-center">
                <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-100 text-brand-700">
                  <Building2 size={24} />
                </div>
                <h2 className="text-lg font-semibold text-slate-900">What would you like to book?</h2>
                <p className="mt-2 max-w-md text-sm text-slate-500">
                  Ask in plain English. DeskDibs will extract your intent, run the reservation in the
                  backend, and confirm with real booking details.
                </p>
              </div>
            )}

            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                  <Loader2 size={16} className="animate-spin" />
                  Processing your request...
                </div>
              </div>
            )}

            <div ref={scrollRef} />
          </div>

          <form
            onSubmit={handleSubmit}
            className="border-t border-slate-200 bg-white px-4 py-4 sm:px-6"
          >
            <div className="flex gap-3">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Book a desk for tomorrow..."
                disabled={loading}
                className="input-field"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="btn-primary shrink-0 px-4"
              >
                {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                Send
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
