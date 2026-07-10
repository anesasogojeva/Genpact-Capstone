import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { format, parseISO } from 'date-fns';
import {
  Bot,
  Building2,
  CalendarDays,
  CalendarCheck,
  CalendarX2,
  ChevronRight,
  Clock3,
  Loader2,
  MessageCircle,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  Send,
  Sparkles,
  Trash2,
  Users,
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

const QUICK_ACTIONS = [
  {
    label: 'Book a desk',
    description: 'Reserve a desk or workspace',
    prompt: 'Book a desk for tomorrow',
    icon: Building2,
    accent: 'bg-blue-50 text-blue-700 ring-blue-100',
  },
  {
    label: 'Find colleagues',
    description: 'See where teammates are sitting',
    prompt: 'Where is Alex sitting tomorrow?',
    icon: Users,
    accent: 'bg-emerald-50 text-emerald-700 ring-emerald-100',
  },
  {
    label: 'Check availability',
    description: 'Search desks for a date',
    prompt: 'Search desks for tomorrow',
    icon: CalendarDays,
    accent: 'bg-violet-50 text-violet-700 ring-violet-100',
  },
  {
    label: 'Cancel reservation',
    description: 'Cancel an existing booking',
    prompt: 'Cancel my reservation for tomorrow',
    icon: CalendarX2,
    accent: 'bg-rose-50 text-rose-700 ring-rose-100',
  },
];

const CAPABILITIES = [
  ['Book desks', 'Reserve a desk for yourself'],
  ['Team location', 'Find where colleagues sit'],
  ['Availability', 'Check desks or rooms'],
  ['Manage bookings', 'Modify or cancel reservations'],
];

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
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white shadow-sm">
          <Bot size={16} />
        </div>
      )}
      <div
        className={`max-w-[92%] px-4 py-3 shadow-sm sm:max-w-[76%] ${
          isUser
            ? 'rounded-2xl rounded-br-md bg-brand-600 text-white'
            : success
              ? 'rounded-2xl rounded-tl-md border border-emerald-200 bg-emerald-50 text-slate-900'
              : info
                ? 'rounded-2xl rounded-tl-md border border-sky-200 bg-sky-50 text-slate-900'
                : 'rounded-2xl rounded-tl-md border border-slate-200 bg-white text-slate-900'
        }`}
      >
        {!isUser && (
          <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase text-slate-500">
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
      {isUser && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-900 text-xs font-semibold text-white shadow-sm">
          You
        </div>
      )}
    </div>
  );
}

function QuickActionButton({ action, disabled, onSelect }) {
  const Icon = action.icon;

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onSelect(action.prompt)}
      className="group flex w-full items-center gap-3 rounded-lg border border-slate-200 bg-white p-3 text-left transition hover:border-brand-200 hover:bg-brand-50/60 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ring-1 ${action.accent}`}>
        <Icon size={17} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-slate-900">{action.label}</span>
        <span className="block truncate text-xs text-slate-500">{action.description}</span>
      </span>
      <ChevronRight size={16} className="text-slate-300 transition group-hover:text-brand-600" />
    </button>
  );
}

function PromptChip({ prompt, disabled, onSelect }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onSelect(prompt)}
      className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-brand-300 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {prompt}
    </button>
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
        subtitle="A focused workspace for reservations, availability, and colleague seating"
        action={
          <Link to="/reservations" className="btn-secondary">
            <CalendarCheck size={16} />
            My Reservations
          </Link>
        }
      />

      <div className="flex min-h-0 flex-1 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-card">
        {sidebarOpen && (
          <aside className="flex w-72 shrink-0 flex-col border-r border-slate-200 bg-slate-50">
            <div className="border-b border-slate-200 p-4">
              <button
                type="button"
                onClick={handleNewChat}
                className="btn-primary w-full rounded-lg py-2.5"
              >
                <MessageSquarePlus size={16} />
                New chat
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-3">
              <p className="px-1 pb-2 text-[11px] font-semibold uppercase text-slate-500">
                Previous chats
              </p>
              {sortedConversations.map((conversation) => {
                const isActive = conversation.id === chatState.activeConversationId;
                return (
                  <div
                    key={conversation.id}
                    className={`group mb-1 flex items-start gap-1 rounded-lg border transition ${
                      isActive
                        ? 'border-brand-200 bg-white shadow-sm'
                        : 'border-transparent hover:border-slate-200 hover:bg-white'
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
                      className="mr-2 mt-2 rounded-md p-1.5 text-slate-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover:opacity-100 focus:opacity-100"
                      aria-label="Delete chat"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                );
              })}
            </div>

            <div className="border-t border-slate-200 px-4 py-3 text-[11px] text-slate-500">
              Saved on this device only
            </div>
          </aside>
        )}

        <main className="flex min-w-0 flex-1 flex-col bg-white">
          <div className="border-b border-slate-200 bg-white px-4 py-3 sm:px-5">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setSidebarOpen((open) => !open)}
                className="rounded-lg border border-slate-200 bg-white p-2 text-slate-600 hover:bg-slate-50"
                aria-label={sidebarOpen ? 'Hide chat history' : 'Show chat history'}
              >
                {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
              </button>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-600 text-white">
                <MessageCircle size={18} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="truncate font-semibold text-slate-900">
                  {activeConversation?.title ?? 'DeskDibs workspace assistant'}
                  </p>
                  {loading && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                      <Loader2 size={12} className="animate-spin" />
                      Thinking
                    </span>
                  )}
                </div>
                <p className="truncate text-sm text-slate-500">
                  Ask for bookings, cancellations, availability, or teammate locations.
                  {!canBookRooms(user?.role) && (
                    <span className="pl-1 text-amber-700">Rooms require team leader or manager access.</span>
                  )}
                </p>
              </div>
            </div>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto bg-slate-50 px-4 py-5 sm:px-6">
            {messages.length === 0 && !loading && (
              <div className="mx-auto flex min-h-full max-w-3xl flex-col justify-center py-6">
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white shadow-sm">
                  <Sparkles size={22} />
                </div>
                <h2 className="text-2xl font-semibold text-slate-950">What should DeskDibs handle?</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                  Start with a direct request. The assistant will confirm the action, show useful details,
                  and keep the booking thread available in your chat history.
                </p>
                <div className="mt-6 grid gap-3 sm:grid-cols-2">
                  {QUICK_ACTIONS.map((action) => (
                    <QuickActionButton
                      key={action.label}
                      action={action}
                      disabled={loading}
                      onSelect={submitMessage}
                    />
                  ))}
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  {suggestedPrompts.slice(0, 5).map((prompt) => (
                    <PromptChip
                      key={prompt}
                      prompt={prompt}
                      disabled={loading}
                      onSelect={submitMessage}
                    />
                  ))}
                </div>
              </div>
            )}

            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="inline-flex items-center gap-2 rounded-2xl rounded-tl-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
                  <Loader2 size={16} className="animate-spin" />
                  Processing your request...
                </div>
              </div>
            )}

            <div ref={scrollRef} />
          </div>

          <form
            onSubmit={handleSubmit}
            className="border-t border-slate-200 bg-white px-4 py-3 sm:px-5"
          >
            <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-2 focus-within:border-brand-300 focus-within:bg-white focus-within:ring-2 focus-within:ring-brand-600/10">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Ask DeskDibs to book, search, cancel, or find a colleague..."
                disabled={loading}
                className="min-h-10 flex-1 border-0 bg-transparent px-2 text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="btn-primary h-10 shrink-0 rounded-lg px-4"
              >
                {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                Send
              </button>
            </div>
          </form>
        </main>

        <aside className="hidden w-80 shrink-0 flex-col border-l border-slate-200 bg-white xl:flex">
          <div className="border-b border-slate-200 p-5">
            <p className="text-sm font-semibold text-slate-900">Quick actions</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Use these to start a structured request without remembering exact wording.
            </p>
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {QUICK_ACTIONS.map((action) => (
              <QuickActionButton
                key={action.label}
                action={action}
                disabled={loading}
                onSelect={submitMessage}
              />
            ))}

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                <Clock3 size={16} className="text-brand-600" />
                Assistant can help with
              </div>
              <div className="mt-3 space-y-3">
                {CAPABILITIES.map(([title, description]) => (
                  <div key={title}>
                    <p className="text-xs font-semibold text-slate-800">{title}</p>
                    <p className="text-xs text-slate-500">{description}</p>
                  </div>
                ))}
              </div>
            </div>

            {!canBookRooms(user?.role) && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-800">
                Meeting room booking is available for team leader and manager accounts.
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
