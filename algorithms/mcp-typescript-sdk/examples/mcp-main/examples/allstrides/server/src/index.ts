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

import express from 'express';
import http from 'http';
import WebSocket from 'ws';
import cors from 'cors';
import path from 'path';
import jwt from 'jsonwebtoken';
import { connectDB } from './database';
import authRoutes from './routes/auth';
import userRoutes from './routes/users';
import eventRoutes from './routes/events';
import chatRoutes from './routes/chat';
import { User, Message } from './models';

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ noServer: true }); // Attach manually for auth handling

const args = process.argv.slice(2);
const portArgIndex = args.indexOf('--port');
const portArg = portArgIndex !== -1 ? args[portArgIndex + 1] : undefined;

const PORT = portArg || process.env.PORT || 8080;
const SECRET_KEY = process.env.SECRET_KEY || "SECRET_KEY_FOR_DEV_ONLY";

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true })); // Support form-urlencoded for login

// Connect Database
connectDB();

// API Routes
app.use('/api/auth', authRoutes);
app.use('/api/users', userRoutes);
app.use('/api/events', eventRoutes);
app.use('/api/chat', chatRoutes); // /api/chat/history

// WebSocket Upgrade & Auth
server.on('upgrade', (request, socket, head) => {
  const url = new URL(request.url!, `http://${request.headers.host}`);
  if (url.pathname === '/api/chat/ws') {
    const token = url.searchParams.get('token');
    
    if (!token) {
      socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
      socket.destroy();
      return;
    }

    jwt.verify(token, SECRET_KEY, async (err: any, decoded: any) => {
      if (err) {
        socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
        socket.destroy();
        return;
      }

      const user = await User.findOne({ where: { email: decoded.sub } });
      if (!user) {
        socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
        socket.destroy();
        return;
      }

      // Pass user to connection
      wss.handleUpgrade(request, socket, head, (ws) => {
        wss.emit('connection', ws, request, user);
      });
    });
  } else {
    socket.destroy();
  }
});

// WebSocket Logic
wss.on('connection', (ws: WebSocket & { user?: any }, request: http.IncomingMessage, user: any) => {
  ws.user = user;
  // console.log(`User connected: ${user.nickname}`);

  ws.on('message', async (message: string) => {
    try {
        const content = message.toString(); // message is Buffer
        
        // Save to DB
        const newMessage = await Message.create({
            content,
            owner_id: user.id,
            created_at: new Date()
        });

        // Broadcast to all clients
        const msgData = JSON.stringify({
            content: newMessage.content,
            owner: {
                nickname: user.nickname,
                id: user.id
            },
            created_at: newMessage.created_at
        });

        wss.clients.forEach((client) => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(msgData);
            }
        });
    } catch (e) {
        console.error("WebSocket error:", e);
    }
  });

  ws.on('close', () => {
    // console.log('Client disconnected');
  });
});

// Static Files (Frontend)
const frontendBuildPath = path.join(__dirname, '..', '..', 'frontend', 'build');

// Serve static assets (js, css, etc.)
app.use('/static', express.static(path.join(frontendBuildPath, 'static')));

// Serve root files (favicon, manifest, etc.)
app.use(express.static(frontendBuildPath));

// SPA Fallback: for any other request, send index.html
app.get(/.*/, (req, res) => {
  // Don't intercept API calls if they 404'd above
  if (req.path.startsWith('/api')) {
      return res.status(404).json({ detail: "Not Found" });
  }
  res.sendFile(path.join(frontendBuildPath, 'index.html'));
});

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
