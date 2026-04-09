/*
 * Copyright 2026 Google LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * This program was created with help of Gemini CLI
 */


import React, { useState, useEffect, useRef } from 'react';
import { Box, TextField, Button, List, ListItem, ListItemText, Paper, Typography } from '@mui/material';
import apiClient from '../../apiClient';

interface Message {
  content: string;
  owner: {
    nickname: string;
  };
  created_at: string;
}

const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const messagesEndRef = useRef<null | HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await apiClient.get('/api/chat/history');
        setMessages(response.data);
      } catch (error) {
        console.error('Failed to fetch chat history:', error);
      }
    };
    fetchHistory();

    const token = localStorage.getItem('token');

    if (!token) {
      console.log("No token found, skipping WebSocket connection");
      return;
    }
    
    let wsUrl;
    if (process.env.REACT_APP_API_URL) {
        wsUrl = process.env.REACT_APP_API_URL.replace(/^http/, 'ws') + '/api/chat/ws';
    } else {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        wsUrl = `${protocol}//${window.location.host}/api/chat/ws`;
    }

    const socket = new WebSocket(`${wsUrl}?token=${token}`);
    
    socket.onopen = () => {
      console.log('WebSocket Connected');
      setIsConnected(true);
    };

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        setMessages((prevMessages) => [...prevMessages, message]);
      } catch (e) {
        console.error("Error parsing message", e);
      }
    };

    socket.onclose = (event) => {
        console.log("WebSocket Disconnected", event.code, event.reason);
        setIsConnected(false);
    }

    setWs(socket);

    return () => {
      socket.close();
    };
  }, []);

  const sendMessage = () => {
    if (ws && ws.readyState === WebSocket.OPEN && input) {
      ws.send(input);
      setInput('');
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', p: 2 }}>
      <Paper sx={{ flexGrow: 1, overflow: 'auto', p: 2, mb: 2 }}>
        <List>
          {messages.map((msg, index) => (
            <ListItem key={index} alignItems="flex-start">
              <ListItemText
                primary={
                  <React.Fragment>
                    <Typography
                      sx={{ display: 'inline', fontWeight: 'bold', mr: 1 }}
                      component="span"
                      variant="body2"
                      color="text.primary"
                    >
                      {msg.owner ? msg.owner.nickname : 'Unknown'}
                    </Typography>
                    <Typography
                      sx={{ display: 'inline' }}
                      component="span"
                      variant="caption"
                      color="text.secondary"
                    >
                       - {new Date(msg.created_at).toLocaleString()}
                    </Typography>
                  </React.Fragment>
                }
                secondary={
                  <Typography
                    component="span"
                    variant="body1"
                    color="text.primary"
                    sx={{ display: 'block', mt: 0.5 }}
                  >
                    {msg.content}
                  </Typography>
                }
              />
            </ListItem>
          ))}
          <div ref={messagesEndRef} />
        </List>
      </Paper>
      <Box sx={{ display: 'flex' }}>
        <TextField
          fullWidth
          variant="outlined"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          placeholder={isConnected ? "Type a message..." : "Connecting..."}
          disabled={!isConnected}
        />
        <Button 
          variant="contained" 
          color="primary" 
          onClick={sendMessage} 
          sx={{ ml: 1 }}
          disabled={!isConnected}
        >
          Send
        </Button>
      </Box>
    </Box>
  );
};

export default ChatInterface;
