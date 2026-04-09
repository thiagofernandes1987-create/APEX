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
import { User } from '../models';
import { authenticateToken, AuthRequest } from '../middleware/auth';

const router = express.Router();

// Get Current User
router.get('/me', authenticateToken, async (req: AuthRequest, res: Response) => {
  try {
    const email = req.user.sub;
    const user = await User.findOne({ where: { email } });
    if (!user) return res.status(404).json({ detail: "User not found" });
    res.json(user);
  } catch (err) {
    res.status(500).json({ error: 'Server error' });
  }
});

// Update Current User
router.put('/me', authenticateToken, async (req: AuthRequest, res: Response) => {
  try {
    const email = req.user.sub;
    const { nickname, profile_picture_url } = req.body;
    
    const user = await User.findOne({ where: { email } });
    if (!user) return res.status(404).json({ detail: "User not found" });

    user.nickname = nickname;
    if (profile_picture_url !== undefined) {
      user.profile_picture_url = profile_picture_url;
    }
    await user.save();
    
    res.json(user);
  } catch (err) {
    res.status(500).json({ error: 'Server error' });
  }
});

export default router;
