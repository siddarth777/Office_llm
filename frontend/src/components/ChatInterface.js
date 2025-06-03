import React, { useState, useRef } from 'react';
import { Send, Paperclip, LogOut, User, Moon, Sun } from 'lucide-react';
import ChatMessage from './ChatMessage';

const ChatInterface = ({ user, onLogout, darkMode, toggleDarkMode }) => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: `Hello ${user?.name}! I'm V, an AI assistant. How can I help you today?`,
      sender: 'claude',
      timestamp: new Date()
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const fileInputRef = useRef(null);

  const handleSendMessage = (e) => {
    e.preventDefault();
    
    if (!inputText.trim()) return;

    const userMessage = {
      id: Date.now(),
      text: inputText,
      sender: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setIsTyping(true);

    // Simulate Claude's response
    setTimeout(() => {
      const claudeResponse = {
        id: Date.now() + 1,
        text: "I understand your message. This is a simulated response from V. In a real implementation, this would connect to the V API to provide intelligent responses.",
        sender: 'claude',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, claudeResponse]);
      setIsTyping(false);
    }, 1500);
  };

  const handleFileAttach = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      console.log('File selected:', file.name);
      // Here you would handle file upload
      alert(`File "${file.name}" selected. File upload functionality would be implemented here.`);
    }
  };

  return (
    <div className="chat-container">
      <header className="chat-header">
        <div className="header-content">
          <h1>V Chat</h1>
          <div className="user-info">
            <button 
              onClick={toggleDarkMode}
              className="dark-mode-toggle header-toggle"
              title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {darkMode ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <span className="user-name">
              <User size={16} />
              {user?.name}
            </span>
            <button onClick={onLogout} className="logout-button">
              <LogOut size={16} />
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="chat-messages">
        {messages.map(message => (
          <ChatMessage key={message.id} message={message} />
        ))}
        {isTyping && (
          <div className="typing-indicator">
            <div className="typing-message">
              <div className="avatar claude-avatar">V</div>
              <div className="typing-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSendMessage} className="chat-input-form">
        <div className="input-container">
          <button
            type="button"
            onClick={handleFileAttach}
            className="attach-button"
            title="Attach file"
          >
            <Paperclip size={20} />
          </button>
          
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Message V..."
            className="chat-input"
          />
          
          <button 
            type="submit" 
            className="send-button"
            disabled={!inputText.trim()}
            title="Send message"
          >
            <Send size={20} />
          </button>
        </div>
        
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          accept="*/*"
        />
      </form>
    </div>
  );
};

export default ChatInterface;