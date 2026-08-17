import { useCallback, useEffect, useRef, useState } from "react";
import {
  createAssistantConversation,
  getAssistantConversation,
  getAssistantConversations,
  sendAssistantMessage,
} from "../services/assistantService";
import { getApiErrorMessage } from "../utils/apiError";

const quickPrompts = [
  "What is the lowest price for Samsung Galaxy A55?",
  "Compare Samsung Galaxy A55 and Apple iPhone 15",
  "Should I buy Samsung Galaxy A55 now or wait?",
  "Recommend alternatives to Apple iPhone 15",
];

function AssistantPage() {
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [draft, setDraft] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);

  const loadConversation = useCallback(async (conversationId) => {
    setError("");

    try {
      setActiveConversation(
        await getAssistantConversation(conversationId),
      );
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    }
  }, []);

  const loadWorkspace = useCallback(async () => {
    setIsLoading(true);
    setError("");

    try {
      const data = await getAssistantConversations();
      const items = Array.isArray(data?.items) ? data.items : [];
      setConversations(items);

      if (items[0]) {
        await loadConversation(items[0].id);
      }
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setIsLoading(false);
    }
  }, [loadConversation]);

  useEffect(() => {
    const timeoutId = window.setTimeout(loadWorkspace, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadWorkspace]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConversation?.messages]);

  async function handleNewConversation() {
    setActiveConversation(null);
    setDraft("");
    setError("");
  }

  async function handleSend(event) {
    event?.preventDefault();
    const content = draft.trim();

    if (!content || isSending) {
      return;
    }

    setIsSending(true);
    setError("");

    try {
      let conversationId = activeConversation?.id;

      if (!conversationId) {
        const created = await createAssistantConversation();
        conversationId = created.id;
        setConversations((current) => [created, ...current]);
      }

      setDraft("");
      await sendAssistantMessage(conversationId, content);
      const [detail, listData] = await Promise.all([
        getAssistantConversation(conversationId),
        getAssistantConversations(),
      ]);
      setActiveConversation(detail);
      setConversations(listData.items || []);
    } catch (requestError) {
      setDraft(content);
      setError(getApiErrorMessage(requestError));
    } finally {
      setIsSending(false);
    }
  }

  function applyPrompt(prompt) {
    setDraft(prompt);
  }

  const messages = activeConversation?.messages || [];

  return (
    <section className="min-h-[calc(100vh-145px)] bg-slate-50 py-10">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">Grounded shopping assistant</p>
          <h1 className="mt-3 text-4xl font-black tracking-[-0.04em] text-slate-950">Ask VEXTRO about stored products and prices</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">Responses use VEXTRO catalog, marketplace offers and price history. The assistant will clarify missing products instead of inventing prices.</p>
        </div>

        <div className="grid min-h-[680px] overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl lg:grid-cols-[300px_1fr]">
          <aside className="border-b border-slate-200 bg-slate-950 p-5 text-white lg:border-b-0 lg:border-r">
            <button type="button" onClick={handleNewConversation} className="min-h-12 w-full rounded-xl bg-blue-600 px-4 text-sm font-black">+ New conversation</button>
            <p className="mt-6 text-xs font-black uppercase tracking-wide text-slate-400">Conversation history</p>
            <div className="mt-3 grid gap-2">
              {conversations.map((conversation) => (
                <button key={conversation.id} type="button" onClick={() => loadConversation(conversation.id)} className={`rounded-xl p-3 text-left text-sm font-bold transition ${activeConversation?.id === conversation.id ? "bg-white text-slate-950" : "bg-white/5 text-slate-300 hover:bg-white/10"}`}>
                  <span className="line-clamp-2">{conversation.title}</span>
                </button>
              ))}
              {!isLoading && conversations.length === 0 ? <p className="rounded-xl border border-white/10 p-4 text-xs leading-6 text-slate-400">Your saved conversations will appear here.</p> : null}
            </div>
          </aside>

          <div className="flex min-h-[680px] flex-col">
            <div className="flex-1 overflow-y-auto p-5 sm:p-8">
              {isLoading ? <div className="h-36 animate-pulse rounded-2xl bg-slate-100" /> : null}
              {!isLoading && messages.length === 0 ? (
                <div className="mx-auto max-w-3xl py-10 text-center">
                  <span className="mx-auto grid size-16 place-items-center rounded-2xl bg-blue-100 text-3xl">V</span>
                  <h2 className="mt-5 text-2xl font-black text-slate-950">Start with a grounded question</h2>
                  <div className="mt-7 grid gap-3 sm:grid-cols-2">
                    {quickPrompts.map((prompt) => <button key={prompt} type="button" onClick={() => applyPrompt(prompt)} className="rounded-2xl border border-slate-200 p-4 text-left text-sm font-semibold leading-6 text-slate-700 transition hover:border-blue-300 hover:bg-blue-50">{prompt}</button>)}
                  </div>
                </div>
              ) : null}

              <div className="space-y-5">
                {messages.map((message) => (
                  <article key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[85%] rounded-2xl px-5 py-4 text-sm leading-7 ${message.role === "user" ? "bg-blue-600 text-white" : "border border-slate-200 bg-slate-50 text-slate-800"}`}>
                      <p>{message.content}</p>
                      {message.role === "assistant" && message.data_timestamp ? <p className="mt-2 text-[10px] font-bold uppercase tracking-wide text-slate-400">Data checked {new Date(message.data_timestamp).toLocaleString("en-PK")}</p> : null}
                    </div>
                  </article>
                ))}
                <div ref={endRef} />
              </div>
            </div>

            <form onSubmit={handleSend} className="border-t border-slate-200 bg-white p-4 sm:p-6">
              {error ? <div className="mb-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700" role="alert">{error}</div> : null}
              <div className="flex gap-3">
                <textarea value={draft} onChange={(event) => setDraft(event.target.value)} rows="2" maxLength="2000" placeholder="Ask about a product, comparison, history, buy timing or alert..." className="min-h-14 flex-1 resize-none rounded-2xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" />
                <button type="submit" disabled={isSending || !draft.trim()} className="min-w-24 rounded-2xl bg-blue-600 px-5 text-sm font-black text-white disabled:opacity-50">{isSending ? "Sending..." : "Send"}</button>
              </div>
              <p className="mt-2 text-xs text-slate-500">VEXTRO does not invent missing prices or guarantee future market movements.</p>
            </form>
          </div>
        </div>
      </div>
    </section>
  );
}

export default AssistantPage;
