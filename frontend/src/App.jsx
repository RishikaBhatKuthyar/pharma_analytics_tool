// App.jsx
// Main React component — the chat interface for the Pharma Analytics Tool
// Users type questions, get AI-powered answers backed by real data

import { useState, useRef, useEffect } from "react";
import axios from "axios";

// API base URL — points to our FastAPI backend
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ─── Individual Message Component ───────────────────────────────────────────

function Message({ msg }) {
  const [showSQL, setShowSQL] = useState(false);
  const [showData, setShowData] = useState(false);

  // User message — simple right-aligned bubble
  if (msg.type === "user") {
    return (
      <div style={styles.userMessageWrapper}>
        <div style={styles.userBubble}>{msg.text}</div>
      </div>
    );
  }

  // Loading message — animated dots while waiting
  if (msg.type === "loading") {
    return (
      <div style={styles.botMessageWrapper}>
        <div style={styles.botIcon}>⚗️</div>
        <div style={styles.loadingBubble}>
          <span className="dot" />
          <span className="dot" />
          <span className="dot" />
        </div>
      </div>
    );
  }

  // Error message
  if (msg.type === "error") {
    return (
      <div style={styles.botMessageWrapper}>
        <div style={styles.botIcon}>⚗️</div>
        <div style={styles.errorBubble}>{msg.text}</div>
      </div>
    );
  }

  // Answer message — shows answer, collapsible SQL and data table
  return (
    <div style={styles.botMessageWrapper}>
      <div style={styles.botIcon}>⚗️</div>
      <div style={styles.answerWrapper}>

        {/* Plain English Answer */}
        <div style={styles.answerBubble}>{msg.answer}</div>

        {/* Single number highlight — shows big number when result is one row one column */}
        {msg.data && msg.data.length === 1 && Object.keys(msg.data[0]).length === 1 && (
          <div style={styles.bigNumberCard}>
            <div style={styles.bigNumber}>
              {Object.values(msg.data[0])[0].toLocaleString()}
            </div>
            <div style={styles.bigNumberLabel}>
              {Object.keys(msg.data[0])[0].replace(/_/g, " ").toUpperCase()}
            </div>
          </div>
        )}

        {/* Collapsible SQL Section — only show if SQL exists */}
        {msg.sql && msg.sql.length > 0 && (
          <>
            <button
              style={styles.toggleButton}
              onClick={() => setShowSQL(!showSQL)}
            >
              {showSQL ? "▼" : "▶"} SQL Query
            </button>
            {showSQL && (
              <pre style={styles.sqlBlock}>{msg.sql}</pre>
            )}
          </>
        )}

        {/* Collapsible Data Table — only show if data exists */}
        {msg.data && msg.data.length > 0 && (
          <>
            <button
              style={styles.toggleButton}
              onClick={() => setShowData(!showData)}
            >
              {showData ? "▼" : "▶"} Raw Data ({msg.data.length} rows)
            </button>
            {showData && <DataTable data={msg.data} />}
          </>
        )}

      </div>
    </div>
  );
}

// ─── Data Table Component ────────────────────────────────────────────────────

function DataTable({ data }) {
  if (!data || data.length === 0) return null;

  const columns = Object.keys(data[0]);

  return (
    <div style={styles.tableWrapper}>
      <table style={styles.table}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col} style={styles.th}>
                {col.replace(/_/g, " ").toUpperCase()}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} style={i % 2 === 0 ? styles.trEven : styles.trOdd}>
              {columns.map((col) => (
                <td key={col} style={styles.td}>
                  {row[col] === null || row[col] === undefined
                    ? "0"
                    : typeof row[col] === "number"
                    ? Number.isInteger(row[col])
                      ? row[col].toLocaleString()
                      : parseFloat(row[col].toFixed(1)).toLocaleString()
                    : row[col]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Suggested Questions Component ──────────────────────────────────────────

function SuggestedQuestions({ onSelect }) {
  const questions = [
    "Which rep had the most completed calls in Q4 2024?",
    "What is the payor mix for Mountain Hospital?",
    "Which doctor has the highest market share in 2025Q1?",
    "List all Tier A doctors and how many times they were visited in 2024",
  ];

  return (
    <div style={styles.suggestionsWrapper}>
      <p style={styles.suggestionsLabel}>Try asking:</p>
      <div style={styles.suggestionsList}>
        {questions.map((q, i) => (
          <button
            key={i}
            style={styles.suggestionChip}
            onClick={() => onSelect(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
  // ─── Login Screen Component ──────────────────────────────────────────────────

const loginInputStyle = {
  backgroundColor: "#0f1117",
  border: "1px solid #2a2d36",
  color: "#e8e6e0",
  padding: "10px 14px",
  borderRadius: "8px",
  fontSize: "14px",
  outline: "none",
};

function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!email.trim() || !password.trim()) return;
    setLoading(true);
    setError("");
    try {
      const endpoint = isRegister ? "/register" : "/login";
      const body = isRegister ? { email, password, name } : { email, password };
      const res = await axios.post(`${API_URL}${endpoint}`, body);
      onLogin(res.data.token, res.data.name);
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", height: "100vh", backgroundColor: "#0f1117", gap: "24px" }}>
      <h1 style={{ color: "#e8c97a", fontFamily: "Georgia, serif", fontSize: "28px" }}>
        ⚗️ Pharma Analytics
      </h1>
      <div style={{ backgroundColor: "#1a1d26", border: "1px solid #2a2d36",
        borderRadius: "12px", padding: "32px", width: "340px", display: "flex",
        flexDirection: "column", gap: "14px" }}>
        <h2 style={{ color: "#e8e6e0", margin: 0, fontSize: "18px", fontFamily: "Georgia, serif" }}>
          {isRegister ? "Create account" : "Sign in"}
        </h2>
        {isRegister && (
          <input placeholder="Your name" value={name}
            onChange={e => setName(e.target.value)} style={loginInputStyle} />
        )}
        <input placeholder="Email" type="email" value={email}
          onChange={e => setEmail(e.target.value)} style={loginInputStyle} />
        <input placeholder="Password" type="password" value={password}
          onChange={e => setPassword(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSubmit()}
          style={loginInputStyle} />
        {error && <p style={{ color: "#f87171", fontSize: "13px", margin: 0 }}>{error}</p>}
        <button onClick={handleSubmit} disabled={loading}
          style={{ backgroundColor: "#e8c97a", color: "#0f1117", border: "none",
            padding: "12px", borderRadius: "8px", fontSize: "14px",
            fontWeight: "700", cursor: "pointer", opacity: loading ? 0.6 : 1 }}>
          {loading ? "..." : isRegister ? "Create account" : "Sign in"}
        </button>
        <button onClick={() => { setIsRegister(!isRegister); setError(""); }}
          style={{ background: "none", border: "none", color: "#6b7280",
            fontSize: "13px", cursor: "pointer", padding: 0 }}>
          {isRegister ? "Already have an account? Sign in" : "No account? Register"}
        </button>
      </div>
      <p style={{ color: "#6b7280", fontSize: "12px" }}>
        Demo: demo@pharmademo.com / pharma2024
      </p>
    </div>
  );
}


// ─── Main App Component ──────────────────────────────────────────────────────

export default function App() {
  // Load messages from localStorage on startup — persists across page refresh
  const [authToken, setAuthToken] = useState(() => localStorage.getItem("pharma_auth_token"));
  const [userName, setUserName] = useState(() => localStorage.getItem("pharma_user_name") || "");

  const handleLogin = (token, name) => {
    localStorage.setItem("pharma_auth_token", token);
    localStorage.setItem("pharma_user_name", name);
    setAuthToken(token);
    setUserName(name);
  };

  const handleLogout = () => {
    localStorage.removeItem("pharma_auth_token");
    localStorage.removeItem("pharma_user_name");
    localStorage.removeItem("pharma_chat_messages");
    localStorage.removeItem("pharma_session_id");
    setAuthToken(null);
    setMessages([]);
};
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem("pharma_chat_messages");
    return saved ? JSON.parse(saved) : [];
  });

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  // // Load conversation history from localStorage on startup
  // const [conversationHistory, setConversationHistory] = useState(() => {
  //   const saved = localStorage.getItem("pharma_chat_history");
  //   return saved ? JSON.parse(saved) : [];
  // });
  // ── NEW session ID for Redis-based history ──
// Generated once per browser — stored in localStorage so it persists across refreshes
// This ID is sent with every request so the backend can fetch history from Redis
  const [sessionId] = useState(() => {
      const existing = localStorage.getItem("pharma_session_id");
      if (existing) return existing;
      const newId = crypto.randomUUID();
      localStorage.setItem("pharma_session_id", newId);
      return newId;
  });

  // Keep conversationHistory state for backwards compatibility
  // But it won't be used when session_id is sent
  const [conversationHistory, setConversationHistory] = useState([]);

  // Auto scroll to bottom when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Save messages to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem("pharma_chat_messages", JSON.stringify(messages));
  }, [messages]);

  // Save conversation history to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem("pharma_chat_history", JSON.stringify(conversationHistory));
  }, [conversationHistory]);

  // Handle question submission
  const handleSubmit = async (question) => {
    const q = question || input.trim();
    if (!q || loading) return;

    setMessages((prev) => [...prev, { type: "user", text: q }]);
    setInput("");
    setLoading(true);
    setMessages((prev) => [...prev, { type: "loading" }]);

    // Timeout safety net — show message if no response in 35 seconds
    const timeoutId = setTimeout(() => {
      setMessages((prev) => [
        ...prev.filter((m) => m.type !== "loading"),
        {
          type: "error",
          text: "This is taking longer than expected. Please try again or rephrase your question.",
        },
      ]);
      setLoading(false);
    }, 35000);

    try {
      // Send question AND conversation history to backend
      const response = await axios.post(
        `${API_URL}/ask`,
        {
          question: q,
          session_id: sessionId,
        },
        {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        }
      );

      clearTimeout(timeoutId);

      // Update conversation history for follow-up questions
      setConversationHistory(response.data.conversation_history);

      setMessages((prev) => [
        ...prev.filter((m) => m.type !== "loading"),
        {
          type: "answer",
          answer: response.data.answer,
          sql: response.data.sql,
          data: response.data.data,
        },
      ]);
    } catch (err) {
      clearTimeout(timeoutId);
      const errorMsg = err.response?.data?.detail?.includes("timed out")
        ? "Request timed out. Please try a simpler question."
        : "Something went wrong. Please try again.";

      setMessages((prev) => [
        ...prev.filter((m) => m.type !== "loading"),
        { type: "error", text: errorMsg },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // Handle Enter key press
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };
  if (!authToken) return <LoginScreen onLogin={handleLogin} />;

  return (

    <div style={styles.appContainer}>

    {/* Header */}
    <div style={styles.header}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={styles.headerTitle}>⚗️ Pharma Analytics</h1>
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <span style={{ color: "#6b7280", fontSize: "12px" }}>👤 {userName}</span>
                  <button style={styles.clearButton} onClick={handleLogout}>
                    Sign out
                  </button>
                  {messages.length > 0 && (
                  <button
                    style={styles.clearButton}
            onClick={async () => {
          const newId = crypto.randomUUID();
          // Clear Redis history for this user
          try {
            await axios.post(`${API_URL}/clear-history`, {}, {
              headers: { Authorization: `Bearer ${authToken}` }
            });
          } catch (e) {
            console.error("Failed to clear Redis history", e);
          }
          setMessages([]);
          setConversationHistory([]);
          localStorage.removeItem("pharma_chat_messages");
          localStorage.removeItem("pharma_session_id");
          localStorage.setItem("pharma_session_id", newId);
          window.location.reload();
        }}
          >
            Clear Chat
          </button>
        )}
        </div>
      </div>
      <p style={styles.headerSubtitle}>
        Ask anything about your sales data in plain English
      </p>
    </div>

      {/* Chat Area */}
      <div style={styles.chatArea}>
        {messages.length === 0 && (
          <SuggestedQuestions onSelect={(q) => handleSubmit(q)} />
        )}
        {messages.map((msg, i) => (
          <Message key={i} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input Area */}
      <div style={styles.inputArea}>
        <input
          style={styles.input}
          type="text"
          placeholder="Ask a question about your pharma data..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button
          style={{
            ...styles.sendButton,
            opacity: loading || !input.trim() ? 0.5 : 1,
          }}
          onClick={() => handleSubmit()}
          disabled={loading || !input.trim()}
        >
          {loading ? "..." : "Ask"}
        </button>
      </div>
    </div>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = {
  appContainer: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    backgroundColor: "#0f1117",
    fontFamily: "'Georgia', serif",
    color: "#e8e6e0",
  },
  header: {
    padding: "24px 32px 16px",
    borderBottom: "1px solid #2a2d36",
    backgroundColor: "#0f1117",
  },
  headerTitle: {
    margin: 0,
    fontSize: "24px",
    fontWeight: "700",
    color: "#e8c97a",
    letterSpacing: "0.5px",
  },
  headerSubtitle: {
    margin: "4px 0 0",
    fontSize: "13px",
    color: "#6b7280",
  },
  chatArea: {
    flex: 1,
    overflowY: "auto",
    padding: "24px 32px",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  userMessageWrapper: {
    display: "flex",
    justifyContent: "flex-end",
  },
  userBubble: {
    backgroundColor: "#1e3a5f",
    color: "#e8e6e0",
    padding: "12px 16px",
    borderRadius: "16px 16px 4px 16px",
    maxWidth: "65%",
    fontSize: "14px",
    lineHeight: "1.5",
  },
  botMessageWrapper: {
    display: "flex",
    alignItems: "flex-start",
    gap: "12px",
  },
  botIcon: {
    fontSize: "24px",
    marginTop: "4px",
    flexShrink: 0,
  },
  answerWrapper: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    maxWidth: "75%",
  },
  answerBubble: {
    backgroundColor: "#1a1d26",
    border: "1px solid #2a2d36",
    color: "#e8e6e0",
    padding: "14px 16px",
    borderRadius: "4px 16px 16px 16px",
    fontSize: "14px",
    lineHeight: "1.6",
  },
  loadingBubble: {
    backgroundColor: "#1a1d26",
    border: "1px solid #2a2d36",
    padding: "16px 20px",
    borderRadius: "4px 16px 16px 16px",
    display: "flex",
    gap: "6px",
    alignItems: "center",
  },
  // dot: {
  //   width: "8px",
  //   height: "8px",
  //   backgroundColor: "#e8c97a",
  //   borderRadius: "50%",
  //   display: "inline-block",
  //   animation: "bounce 0.8s infinite",
  // },
  errorBubble: {
    backgroundColor: "#2d1a1a",
    border: "1px solid #5c2a2a",
    color: "#f87171",
    padding: "12px 16px",
    borderRadius: "4px 16px 16px 16px",
    fontSize: "14px",
  },
  toggleButton: {
    background: "none",
    border: "1px solid #2a2d36",
    color: "#6b7280",
    padding: "4px 10px",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "12px",
    alignSelf: "flex-start",
  },
  sqlBlock: {
    backgroundColor: "#0d1117",
    border: "1px solid #2a2d36",
    color: "#7dd3fc",
    padding: "12px 16px",
    borderRadius: "8px",
    fontSize: "12px",
    overflowX: "auto",
    whiteSpace: "pre-wrap",
    lineHeight: "1.6",
  },
  tableWrapper: {
    overflowX: "auto",
    borderRadius: "8px",
    border: "1px solid #2a2d36",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "13px",
  },
  th: {
    backgroundColor: "#1a1d26",
    color: "#e8c97a",
    padding: "10px 14px",
    textAlign: "left",
    fontWeight: "600",
    letterSpacing: "0.5px",
    fontSize: "11px",
    borderBottom: "1px solid #2a2d36",
  },
  trEven: { backgroundColor: "#0f1117" },
  trOdd: { backgroundColor: "#13161f" },
  td: {
    padding: "10px 14px",
    color: "#e8e6e0",
    borderBottom: "1px solid #1e2028",
  },
  suggestionsWrapper: {
    padding: "40px 0 20px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "16px",
  },
  suggestionsLabel: {
    color: "#6b7280",
    fontSize: "13px",
    margin: 0,
  },
  suggestionsList: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
    justifyContent: "center",
    maxWidth: "700px",
  },
  suggestionChip: {
    backgroundColor: "#1a1d26",
    border: "1px solid #2a2d36",
    color: "#e8e6e0",
    padding: "8px 14px",
    borderRadius: "20px",
    cursor: "pointer",
    fontSize: "13px",
  },
  inputArea: {
    padding: "16px 32px 24px",
    borderTop: "1px solid #2a2d36",
    display: "flex",
    gap: "12px",
    backgroundColor: "#0f1117",
  },
  input: {
    flex: 1,
    backgroundColor: "#1a1d26",
    border: "1px solid #2a2d36",
    color: "#e8e6e0",
    padding: "12px 16px",
    borderRadius: "8px",
    fontSize: "14px",
    outline: "none",
  },
  sendButton: {
    backgroundColor: "#e8c97a",
    color: "#0f1117",
    border: "none",
    padding: "12px 24px",
    borderRadius: "8px",
    fontSize: "14px",
    fontWeight: "700",
    cursor: "pointer",
    transition: "opacity 0.2s",
  },
  clearButton: {
  backgroundColor: "transparent",
  border: "1px solid #2a2d36",
  color: "#6b7280",
  padding: "6px 12px",
  borderRadius: "6px",
  cursor: "pointer",
  fontSize: "12px",
},
bigNumberCard: {
  backgroundColor: "#1a1d26",
  border: "1px solid #e8c97a",
  borderRadius: "12px",
  padding: "20px 28px",
  display: "inline-flex",
  flexDirection: "column",
  alignItems: "center",
  gap: "4px",
},
bigNumber: {
  fontSize: "36px",
  fontWeight: "700",
  color: "#e8c97a",
},
bigNumberLabel: {
  fontSize: "11px",
  color: "#6b7280",
  letterSpacing: "1px",
},
};