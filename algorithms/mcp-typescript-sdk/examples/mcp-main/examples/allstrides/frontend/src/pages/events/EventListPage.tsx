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
import { Container, Box, Typography, Card, CardContent, CardActions, Button, Grid, IconButton, Badge } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
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

const EventListPage: React.FC = () => {
  const [events, setEvents] = useState<Event[]>([]);

  const fetchEvents = async () => {
    try {
      const response = await apiClient.get('/api/events/');
      setEvents(response.data);
    } catch (error) {
      console.error('Failed to fetch events:', error);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, []);

  const handleVote = async (eventId: number) => {
    try {
      const token = localStorage.getItem('token');
      await apiClient.post('/api/events/vote', { event_id: eventId }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchEvents();
    } catch (error) {
      console.error('Failed to vote:', error);
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ marginTop: 8 }}>
        <Typography component="h1" variant="h4" gutterBottom>
          Events
        </Typography>
        <Button component={RouterLink} to="/events/create" variant="contained" color="primary" sx={{ mb: 2 }}>
          Create Event
        </Button>
        <Grid container spacing={4}>
          {events.map((event) => (
            <Grid key={event.id} size={{ xs: 12, sm: 6, md: 4 }}>
              <Card>
                <CardContent>
                  <Typography variant="h5" component="div">
                    {event.title}
                  </Typography>
                  <Typography sx={{ mb: 1.5 }} color="text.secondary">
                    {new Date(event.start_time).toLocaleString()} • {event.distance} {event.unit}
                  </Typography>
                  <Typography variant="body2">
                    {event.description}
                  </Typography>
                </CardContent>
                <CardActions disableSpacing>
                  <Button size="small" component={RouterLink} to={`/events/${event.id}`}>
                    Learn More
                  </Button>
                  <IconButton aria-label="vote" onClick={() => handleVote(event.id)} sx={{ marginLeft: 'auto' }}>
                    <Badge badgeContent={event.vote_count} color="secondary">
                      <ThumbUpIcon />
                    </Badge>
                  </IconButton>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>
    </Container>
  );
};

export default EventListPage;
