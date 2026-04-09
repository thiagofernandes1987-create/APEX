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
import { Container, Box, Typography, Button, Rating, IconButton, Badge } from '@mui/material';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import { useParams } from 'react-router-dom';
import apiClient from '../../apiClient';

interface Event {
  id: number;
  title: string;
  description: string;
  start_time: string;
  distance: number;
  unit: string;
  vote_count: number;
}

const EventDetailPage: React.FC = () => {
  const [event, setEvent] = useState<Event | null>(null);
  const [rating, setRating] = useState<number | null>(0);
  const { eventId } = useParams<{ eventId: string }>();

  const fetchEvent = async () => {
    try {
      const response = await apiClient.get(`/api/events/${eventId}`);
      setEvent(response.data);
    } catch (error) {
      console.error('Failed to fetch event:', error);
    }
  };

  useEffect(() => {
    fetchEvent();
  }, [eventId]);

  const handleRsvp = async () => {
    try {
      const token = localStorage.getItem('token');
      await apiClient.post('/api/events/rsvp', { event_id: eventId }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      console.log('RSVP successful');
    } catch (error) {
      console.error('RSVP failed:', error);
    }
  };

  const handleVote = async () => {
    try {
      const token = localStorage.getItem('token');
      await apiClient.post('/api/events/vote', { event_id: eventId }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchEvent();
    } catch (error) {
      console.error('Failed to vote:', error);
    }
  };

  const handleRating = async (newValue: number | null) => {
    if (newValue === null) return;
    setRating(newValue);
    try {
      const token = localStorage.getItem('token');
      await apiClient.post('/api/events/rate', { event_id: eventId, value: newValue }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      console.log('Rating successful');
    } catch (error) {
      console.error('Rating failed:', error);
    }
  };

  if (!event) {
    return <Typography>Loading...</Typography>;
  }

  return (
    <Container maxWidth="md">
      <Box sx={{ marginTop: 8 }}>
        <Typography component="h1" variant="h4" gutterBottom>
          {event.title}
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          {new Date(event.start_time).toLocaleString()} • {event.distance} {event.unit}
        </Typography>
        <Typography variant="body1" sx={{ mt: 2 }}>
          {event.description}
        </Typography>
        <Box sx={{ mt: 4, display: 'flex', alignItems: 'center', gap: 2 }}>
          <Button variant="contained" color="primary" onClick={handleRsvp}>
            RSVP
          </Button>
          <IconButton aria-label="vote" onClick={handleVote}>
            <Badge badgeContent={event.vote_count} color="secondary">
              <ThumbUpIcon />
            </Badge>
          </IconButton>
        </Box>
        <Box sx={{ mt: 4 }}>
          <Typography component="legend">Rate this event</Typography>
          <Rating
            name="event-rating"
            value={rating}
            onChange={(event, newValue) => {
              handleRating(newValue);
            }}
          />
        </Box>
      </Box>
    </Container>
  );
};

export default EventDetailPage;
