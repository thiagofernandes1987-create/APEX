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
import { Container, Typography, Box, Paper, Button } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';

const MainContent: React.FC = () => {
  return (
    <Container component="main" sx={{ mt: 4, mb: 4 }}>
      <Paper
        sx={{
          position: 'relative',
          backgroundColor: 'grey.800',
          color: '#fff',
          mb: 4,
          backgroundSize: 'cover',
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'center',
          backgroundImage: 'url(/florence-runners.png)',
          minHeight: '400px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          textAlign: 'center',
          p: 4
        }}
      >
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            right: 0,
            left: 0,
            backgroundColor: 'rgba(0,0,0,.5)',
          }}
        />
        <Box sx={{ position: 'relative', zIndex: 1 }}>
          <Typography component="h1" variant="h3" color="inherit" gutterBottom>
            Welcome to AllStrides
          </Typography>
          <Typography variant="h5" color="inherit" paragraph>
            Join the community of runners. Organize events, track your progress, and run your way!
          </Typography>
          <Button variant="contained" color="secondary" component={RouterLink} to="/register">
            Get Started
          </Button>
        </Box>
      </Paper>
      
      <Typography variant="h5" gutterBottom>
        Upcoming Events
      </Typography>
      <Typography variant="body1">
        Check out the <RouterLink to="/events">Events</RouterLink> page to see what's happening near you.
      </Typography>
    </Container>
  );
};

export default MainContent;
