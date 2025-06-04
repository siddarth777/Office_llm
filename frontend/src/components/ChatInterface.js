import React, { useState, useRef } from 'react';
import { Send, Paperclip, LogOut, User, Moon, Sun, Trash2 } from 'lucide-react';
import ChatMessage from './ChatMessage';

const ChatInterface = ({ user, onLogout, darkMode, toggleDarkMode }) => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: `Hello ${user?.name}! I'm V, an AI assistant. How can I help you today?`,
      sender: 'varuna',
      timestamp: new Date()
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const fileInputRef = useRef(null);

  // Initial greeting message
  const getInitialMessage = () => ({
    id: 1,
    text: `Hello ${user?.name}! I'm V, an AI assistant. How can I help you today?`,
    sender: 'varuna',
    timestamp: new Date()
  });

  // Function to convert messages array to string format
  const messagesToString = (messagesArray) => {
    return messagesArray.map(msg => {
      const role = msg.sender === 'user' ? 'User' : 'V';
      return `${role}: ${msg.text}`;
    }).join('\n');
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    const userMessage = {
      id: Date.now(),
      text: inputText,
      sender: 'user',
      timestamp: new Date()
    };

    // Update messages with the new user message
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    
    // Convert chat history to string
    const chatHistoryString = messagesToString(updatedMessages);
    
    const currentInput = inputText;
    setInputText('');
    setIsTyping(true);

    try {
      const response = await fetch('http://127.0.0.1:8000/message', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: currentInput,
          chatHistory: chatHistoryString
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      const apiResponse = {
        id: Date.now() + 1,
        text: data.response || data.message || 'No response received',
        sender: 'varuna',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, apiResponse]);
    } catch (error) {
      console.error('Error sending message:', error);
      
      const errorResponse = {
        id: Date.now() + 1,
        text: 'Sorry, I encountered an error while processing your message. Please try again.',
        sender: 'varuna',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, errorResponse]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleClearChat = () => {
    setMessages([getInitialMessage()]);
    setInputText('');
    setIsTyping(false);
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
              onClick={handleClearChat}
              className="clear-chat-button header-toggle"
              title="Clear chat history"
            >
              <Trash2 size={16} />
            </button>
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
              <div className="avatar varuna-avatar">V</div>
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