import React, { useState, useRef, useEffect } from "react";
import { MessageSquare, Send, X, Bot, Sparkles, Loader2, RefreshCcw } from "lucide-react";
import { Button } from "./ui/button";
import { API_BASE_URL } from "@/services/ibbiService";
import type { Company } from "@/data/types";

interface Message {
  role: "user" | "ai";
  content: string;
}

const AIChatAssistant = ({ company }: { company: any }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    { 
      role: "ai", 
      content: company?.name 
        ? `Hello! I am your **Fintech AI Assistant**. I've analyzed **${company.name}**. How can I help you understand their current risk or financial situation today?`
        : `Hello! I am your **Fintech AI Assistant**. How can I help you with corporate insights or risk analysis today?`
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  useEffect(() => {
    const handleOpenChat = () => setIsOpen(true);
    window.addEventListener('open-ai-chat', handleOpenChat);
    return () => window.removeEventListener('open-ai-chat', handleOpenChat);
  }, []);

  const handleSend = async () => {
    if (!query.trim() || isLoading) return;

    const userQuery = query.trim();
    setQuery("");
    setMessages(prev => [...prev, { role: "user", content: userQuery }]);
    setIsLoading(true);
    setIsTyping(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userQuery, company })
      });

      if (!response.ok) throw new Error("AI Engine offline");
      const data = await response.json();
      
      setMessages(prev => [...prev, { role: "ai", content: data.answer }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: "ai", content: "I apologize, but my reasoning engine is currently experiencing a delay. Please try again in a moment." }]);
    } finally {
      setIsLoading(false);
      setIsTyping(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="group relative flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-tr from-[#81BC06] to-[#A3D93F] text-white shadow-2xl transition-all hover:scale-110 active:scale-95"
        >
          <Sparkles className="h-6 w-6 animate-pulse" />
          <div className="absolute -top-12 -left-32 w-32 scale-0 rounded-lg bg-slate-900 px-3 py-2 text-[10px] font-bold text-white transition-all group-hover:scale-100">
            {company?.name ? `Ask AI about ${company.name}` : "Ask AI Assistant"}
          </div>
        </button>
      )}

      {isOpen && (
        <div className="flex h-[550px] w-full max-w-[400px] flex-col overflow-hidden rounded-2xl border border-slate-200/50 bg-white/95 shadow-2xl backdrop-blur-xl sm:w-[400px]">
          {/* Header */}
          <div className="flex items-center justify-between bg-gradient-to-r from-slate-900 to-slate-800 px-5 py-4 text-white">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/10">
                <Bot className="h-5 w-5 text-[#81BC06]" />
              </div>
              <div>
                <h3 className="text-sm font-black tracking-tight">Fintech AI-IQ</h3>
                <div className="flex items-center gap-1.5 text-[10px] font-bold text-green-400 uppercase">
                  <div className="h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
                  Live Context Analysis
                </div>
              </div>
            </div>
            <button onClick={() => setIsOpen(false)} className="rounded-full p-1.5 hover:bg-white/10">
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4 bg-slate-50/30">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-xs leading-relaxed shadow-sm ${
                  m.role === "user" 
                    ? "bg-[#81BC06] text-white font-medium rounded-tr-none" 
                    : "bg-white border border-slate-100 text-slate-700 rounded-tl-none"
                }`}>
                  {m.content.split("**").map((part, idx) => 
                    idx % 2 === 1 ? <strong key={idx} className="font-black text-slate-900">{part}</strong> : part
                  )}
                </div>
              </div>
            ))}
            {isTyping && (
              <div className="flex justify-start">
                <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm">
                  <Loader2 className="h-4 w-4 animate-spin text-[#81BC06]" />
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="border-t border-slate-100 bg-white p-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="Ask about risk, summary or charges..."
                className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-medium outline-none focus:border-[#81BC06] transition-all"
              />
              <Button 
                onClick={handleSend}
                disabled={isLoading}
                className="rounded-xl bg-[#81BC06] hover:bg-[#6ea105] h-10 w-10 p-0 flex items-center justify-center shadow-lg shadow-[#81BC06]/20"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {["Check Risk", "Summarize Charges"].map(tag => (
                <button 
                  key={tag}
                  onClick={() => { setQuery(tag); }}
                  className="rounded-full bg-slate-100 px-3 py-1 text-[9px] font-bold text-slate-500 uppercase hover:bg-[#81BC06]/10 hover:text-[#81BC06] transition-colors"
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIChatAssistant;
