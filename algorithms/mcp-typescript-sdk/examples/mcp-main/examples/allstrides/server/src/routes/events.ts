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


import express, { Response } from 'express';
import { Event, User, RSVP, Vote, Rating } from '../models';
import { authenticateToken, AuthRequest } from '../middleware/auth';

const router = express.Router();

// Create Event
router.post('/', authenticateToken, async (req: AuthRequest, res: Response) => {
  try {
    const email = req.user.sub;
    const user = await User.findOne({ where: { email } });
    if (!user) return res.status(404).json({ detail: "User not found" });

    const event = await Event.create({
      ...req.body,
      owner_id: user.id
    });
    res.json(event);
  } catch (err) {
    res.status(500).json({ error: 'Server error' });
  }
});

// List Events
router.get('/', async (req, res) => {
  try {
    const { skip = 0, limit = 100 } = req.query;
    const events = await Event.findAll({
      offset: Number(skip),
      limit: Number(limit),
      include: [{ model: Vote, as: 'votes' }]
    });

    // In Python, we calculated vote_count dynamically. 
    // We can do that here or let the frontend handle it if it gets the array.
    // The Python response_model=list[schemas.Event] implied it returned the list.
    // Let's attach vote_count to match the expected schema if possible.
    const eventsWithCount = events.map((e: any) => {
        const json = e.toJSON();
        json.vote_count = e.votes ? e.votes.length : 0;
        return json;
    });

    res.json(eventsWithCount);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Server error' });
  }
});

// Get Event Detail
router.get('/:id', async (req, res) => {
  try {
    const event = await Event.findByPk(req.params.id, {
        include: [{ model: Vote, as: 'votes' }]
    });
    if (!event) return res.status(404).json({ detail: "Event not found" });

    const json: any = event.toJSON();
    json.vote_count = event.votes ? event.votes.length : 0;
    
    res.json(json);
  } catch (err) {
    res.status(500).json({ error: 'Server error' });
  }
});

// Vote
router.post('/vote', authenticateToken, async (req: AuthRequest, res: Response) => {
  try {
    const email = req.user.sub;
    const user = await User.findOne({ where: { email } });
    if (!user) return res.status(404).json({ detail: "User not found" });

    const { event_id } = req.body;

    const existingVote = await Vote.findOne({
      where: { user_id: user.id, event_id }
    });

    if (existingVote) {
      await existingVote.destroy();
      return res.json(existingVote); // Return the deleted vote as confirmation (matches Python behavior approximately)
    }

    const newVote = await Vote.create({
      user_id: user.id,
      event_id
    });
    res.json(newVote);
  } catch (err) {
    res.status(500).json({ error: 'Server error' });
  }
});

// RSVP
router.post('/rsvp', authenticateToken, async (req: AuthRequest, res: Response) => {
  try {
    const email = req.user.sub;
    const user = await User.findOne({ where: { email } });
    if (!user) return res.status(404).json({ detail: "User not found" });

    const { event_id } = req.body; // Add other RSVP fields if schema has them, currently only IDs
    
    const rsvp = await RSVP.create({
        user_id: user.id,
        event_id
    });
    res.json(rsvp);
  } catch (err) {
    res.status(500).json({ error: 'Server error' });
  }
});

// Rate
router.post('/rate', authenticateToken, async (req: AuthRequest, res: Response) => {
  try {
    const email = req.user.sub;
    const user = await User.findOne({ where: { email } });
    if (!user) return res.status(404).json({ detail: "User not found" });

    const { event_id, value } = req.body;
    
    const rating = await Rating.create({
        user_id: user.id,
        event_id,
        value
    });
    res.json(rating);
  } catch (err) {
    res.status(500).json({ error: 'Server error' });
  }
});

export default router;
