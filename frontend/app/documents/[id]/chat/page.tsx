"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { chatService } from "@/services/chat";
import { documentsService } from "@/services/documents";
import type { MessageResponse, DocumentResponse, PassageResponse, SectionResponse } from "@/types/api";
import { Send, ArrowLeft, BookOpen, Search, Menu, MessageSquare, Bookmark, Lightbulb, MapPin, X } from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";

export default function ChatPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [sections, setSections] = useState<SectionResponse[]>([]);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const [showNav, setShowNav] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadData();
  }, [documentId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const loadData = async () => {
    try {
      const docData = await documentsService.get(documentId);
      if (docData.status !== "ready") {
        router.push(`/documents/${documentId}/processing`);
        return;
      }
      setDoc(docData);

      const { sections: sectionsData } = await documentsService.getSections(documentId);
      setSections(sectionsData);

      // Try to load existing conversation
      const { conversations } = await chatService.listConversations(documentId);
      if (conversations.length > 0) {
        const recent = conversations[0];
        setConversationId(recent.id);
        const { messages: msgs } = await chatService.getConversation(recent.id);
        setMessages(msgs);
      }
    } catch (err) {
      console.error("Failed to load chat data", err);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    
    // Add optimistic user message
    const tempUserMsg: MessageResponse = {
      id: Date.now().toString(),
      conversation_id: conversationId || "",
      role: "user",
      content: userMessage,
      created_at: new Date().toISOString()
    };
    
    setMessages(prev => [...prev, tempUserMsg]);
    setIsLoading(true);

    try {
      const res = await chatService.sendMessage(documentId, userMessage, conversationId);
      if (!conversationId) setConversationId(res.conversation_id);
      
      // We don't add the server's user message to avoid duplicate, just add assistant
      setMessages(prev => [...prev, res.message]);
    } catch (err) {
      console.error("Failed to send message", err);
      // Remove optimistic message on fail and show error (simplified)
      setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id));
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  if (!doc) return <div className="h-screen bg-background animate-pulse" />;

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Mobile Nav Toggle */}
      <div className="md:hidden fixed top-4 left-4 z-50 bg-card rounded-lg shadow-sm border border-border p-2 cursor-pointer" onClick={() => setShowNav(!showNav)}>
        {showNav ? <X size={20} /> : <Menu size={20} />}
      </div>

      {/* Sidebar Navigation */}
      <aside className={`
        ${showNav ? "translate-x-0" : "-translate-x-full"}
        md:translate-x-0 fixed md:static inset-y-0 left-0 z-40
        w-72 bg-card border-r border-border transition-transform duration-300 ease-in-out flex flex-col
      `}>
        <div className="p-4 border-b border-border flex items-center justify-between">
          <Link href="/" className="inline-flex items-center text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft size={16} className="mr-2" />
            Library
          </Link>
        </div>

        <div className="p-4 border-b border-border">
          <h2 className="font-semibold text-lg line-clamp-2" title={doc.title}>{doc.title}</h2>
          {doc.author && <p className="text-sm text-muted-foreground mt-1">{doc.author}</p>}
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-4 flex items-center gap-2">
            <BookOpen size={14} /> Contents
          </h3>
          <div className="space-y-1">
            {sections.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">No structure detected.</p>
            ) : (
              sections.map((sec) => (
                <div 
                  key={sec.id} 
                  className={`text-sm py-1.5 px-2 rounded-md hover:bg-secondary cursor-pointer line-clamp-1 transition-colors ${
                    sec.level === 1 ? "font-semibold mt-2" : 
                    sec.level === 2 ? "ml-4 text-foreground/90" : "ml-8 text-muted-foreground"
                  }`}
                  title={sec.title}
                >
                  {sec.title}
                </div>
              ))
            )}
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col h-full bg-background relative w-full">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-8 md:px-12 scroll-smooth">
          <div className="max-w-3xl mx-auto space-y-8 pb-10">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-6 pt-20">
                <div className="bg-primary/10 p-4 rounded-full">
                  <MessageSquare className="w-8 h-8 text-primary" />
                </div>
                <div>
                  <h2 className="text-2xl font-semibold mb-2">Ask {doc.title}</h2>
                  <p className="text-muted-foreground max-w-md mx-auto">
                    Start a conversation with this document. Ask questions, request summaries, or explore specific concepts.
                  </p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-lg mt-8">
                  {["What are the key takeaways?", "Can you summarize the introduction?", "Find quotes about...", "Explain the main concept."].map((prompt, i) => (
                    <button
                      key={i}
                      onClick={() => setInput(prompt)}
                      className="text-left text-sm p-4 rounded-xl border border-border bg-card hover:border-primary/50 hover:shadow-sm transition-all"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, i) => (
                <div key={msg.id || i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[90%] md:max-w-[85%] rounded-2xl p-5 ${
                    msg.role === "user" 
                      ? "bg-primary text-primary-foreground rounded-tr-sm" 
                      : "bg-card border border-border shadow-sm rounded-tl-sm"
                  }`}>
                    
                    {/* User Message */}
                    {msg.role === "user" && (
                      <div className="text-[15px] leading-relaxed whitespace-pre-wrap">{msg.content}</div>
                    )}

                    {/* Assistant Message with Formatting */}
                    {msg.role === "assistant" && (
                      <div className="space-y-6">
                        {/* Render Passages / Citations if available */}
                        {msg.passages && msg.passages.length > 0 && (
                          <div className="bg-secondary/50 rounded-xl p-4 border border-border/50">
                            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5 mb-3">
                              <Search size={14} /> Retrieved Context
                            </h4>
                            <div className="space-y-4">
                              {msg.passages.map((p, pIdx) => (
                                <div key={p.chunk_id || pIdx} className="relative pl-4 border-l-2 border-primary/40">
                                  <div className="font-passage text-[15px] leading-relaxed text-foreground/90 italic mb-2">
                                    "{p.content}"
                                  </div>
                                  <div className="flex items-center gap-2 text-xs text-muted-foreground font-medium">
                                    <MapPin size={12} />
                                    <span>
                                      {[p.source.chapter, p.source.section, p.source.page ? `Page ${p.source.page}` : null]
                                        .filter(Boolean)
                                        .join(" › ") || "Document Source"}
                                    </span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Markdown Content */}
                        <div className="prose prose-stone dark:prose-invert max-w-none text-[15px] leading-relaxed">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                        
                        {/* Action Bar */}
                        <div className="flex items-center gap-3 pt-2 border-t border-border mt-4">
                          <button className="text-xs font-medium text-muted-foreground hover:text-primary transition-colors flex items-center gap-1.5">
                            <Bookmark size={14} /> Bookmark
                          </button>
                          <button 
                            onClick={() => {
                              setInput(`Can you explain that passage in more detail?`);
                            }}
                            className="text-xs font-medium text-muted-foreground hover:text-primary transition-colors flex items-center gap-1.5"
                          >
                            <Lightbulb size={14} /> Discuss Passage
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-card border border-border shadow-sm rounded-2xl rounded-tl-sm p-5 flex items-center gap-3">
                  <span className="flex gap-1">
                    <span className="w-2 h-2 rounded-full bg-primary/40 animate-bounce" style={{ animationDelay: "0ms" }}></span>
                    <span className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: "150ms" }}></span>
                    <span className="w-2 h-2 rounded-full bg-primary/80 animate-bounce" style={{ animationDelay: "300ms" }}></span>
                  </span>
                  <span className="text-sm font-medium text-muted-foreground animate-pulse">Reading document...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="p-4 md:px-12 bg-background/80 backdrop-blur-md border-t border-border">
          <div className="max-w-3xl mx-auto relative">
            <form onSubmit={handleSubmit} className="relative flex items-end shadow-sm bg-card rounded-2xl border border-border focus-within:ring-2 focus-within:ring-primary/20 focus-within:border-primary/50 transition-all">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question about the document..."
                className="w-full max-h-32 min-h-[56px] py-4 pl-5 pr-14 bg-transparent resize-none outline-none text-[15px]"
                rows={1}
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={!input.trim() || isLoading}
                className="absolute right-2 bottom-2 p-2.5 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:bg-muted disabled:text-muted-foreground transition-colors"
              >
                <Send size={18} />
              </button>
            </form>
            <p className="text-center text-[11px] text-muted-foreground mt-3 font-medium">
              FootNote can make mistakes. Always verify information with the source document.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
