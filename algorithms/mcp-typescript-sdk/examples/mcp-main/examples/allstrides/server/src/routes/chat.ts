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
import { Message, User } from '../models';

const router = express.Router();

// Get Chat History
router.get('/history', async (req, res) => {
  try {
    const { skip = 0, limit = 50 } = req.query;
    
    const messages = await Message.findAll({
      order: [['created_at', 'DESC']],
      offset: Number(skip),
      limit: Number(limit),
      include: [{ model: User, as: 'owner', attributes: ['id', 'nickname'] }]
    });

    // Python reversed the list to show oldest first in the UI after fetching newest
    res.json(messages.reverse());
  } catch (err) {
    res.status(500).json({ error: 'Server error' });
  }
});

export default router;
