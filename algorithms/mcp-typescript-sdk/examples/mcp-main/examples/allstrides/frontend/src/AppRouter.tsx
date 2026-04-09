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


import React from 'react';
import { Route, Routes } from 'react-router-dom';
import LoginPage from './pages/auth/LoginPage';
import RegistrationPage from './pages/auth/RegistrationPage';
import PasswordResetRequestPage from './pages/auth/PasswordResetRequestPage';
import ProfilePage from './pages/profile/ProfilePage';
import EventListPage from './pages/events/EventListPage';
import EventDetailPage from './pages/events/EventDetailPage';
import CreateEventPage from './pages/events/CreateEventPage';
import ChatPage from './pages/ChatPage';
import MainContent from './components/layout/MainContent';

const AppRouter: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<MainContent />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegistrationPage />} />
      <Route path="/reset-password" element={<PasswordResetRequestPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/events" element={<EventListPage />} />
      <Route path="/events/create" element={<CreateEventPage />} />
      <Route path="/events/:eventId" element={<EventDetailPage />} />
      <Route path="/chat" element={<ChatPage />} />
    </Routes>
  );
};

export default AppRouter;
