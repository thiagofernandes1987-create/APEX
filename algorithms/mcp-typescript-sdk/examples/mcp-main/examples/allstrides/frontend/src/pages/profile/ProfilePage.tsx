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


import React, { useState, useEffect } from 'react';
import { Container, Box, TextField, Button, Typography, Alert, Link as MuiLink } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import apiClient from '../../apiClient';
import { useAuth } from '../../AuthContext';

const ProfilePage: React.FC = () => {
  const { user, loading: authLoading } = useAuth();
  const [nickname, setNickname] = useState('');
  const [updating, setUpdating] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  useEffect(() => {
    if (user) {
      setNickname(user.nickname);
    }
  }, [user]);

  const handleUpdate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!user) return;

    setUpdating(true);
    setMessage(null);
    try {
      const token = localStorage.getItem('token');
      await apiClient.put('/api/users/me', { nickname }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setMessage({ type: 'success', text: 'Profile updated successfully' });
      // Note: In a real app, you might want to refresh the user in AuthContext here
    } catch (error) {
      console.error('Failed to update profile:', error);
      setMessage({ type: 'error', text: 'Failed to update profile' });
    } finally {
      setUpdating(false);
    }
  };

  if (authLoading) {
    return (
      <Container maxWidth="sm" sx={{ mt: 8 }}>
        <Typography>Loading...</Typography>
      </Container>
    );
  }

  if (!user) {
    return (
      <Container maxWidth="sm" sx={{ mt: 8 }}>
        <Alert severity="warning">
          You are not logged in. Please{' '}
          <MuiLink component={RouterLink} to="/register">
            register
          </MuiLink>{' '}
          or{' '}
          <MuiLink component={RouterLink} to="/login">
            login
          </MuiLink>{' '}
          to view your profile.
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="sm">
      <Box sx={{ marginTop: 8 }}>
        <Typography component="h1" variant="h5">
          My Profile
        </Typography>
        {message && (
          <Alert severity={message.type} sx={{ mt: 2 }}>
            {message.text}
          </Alert>
        )}
        <Box component="form" onSubmit={handleUpdate} noValidate sx={{ mt: 1 }}>
          <TextField
            margin="normal"
            fullWidth
            id="email"
            label="Email Address"
            name="email"
            value={user.email}
            disabled
          />
          <TextField
            margin="normal"
            required
            fullWidth
            name="nickname"
            label="Nickname"
            id="nickname"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
          />
          <Button
            type="submit"
            fullWidth
            variant="contained"
            sx={{ mt: 3, mb: 2 }}
            disabled={updating}
          >
            {updating ? 'Updating...' : 'Update Profile'}
          </Button>
        </Box>
      </Box>
    </Container>
  );
};

export default ProfilePage;
