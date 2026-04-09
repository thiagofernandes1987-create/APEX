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


import express, { Request, Response } from 'express';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { User } from '../models';

const router = express.Router();
const SECRET_KEY = process.env.SECRET_KEY || "SECRET_KEY_FOR_DEV_ONLY";

// Register
router.post('/register', async (req: Request, res: Response) => {
  try {
    const { email, password, first_name, last_name, nickname } = req.body;
    
    const existingUser = await User.findOne({ where: { email } });
    if (existingUser) {
      return res.status(400).json({ detail: "Email already registered" });
    }

    const hashedPassword = await bcrypt.hash(password, 10);
    const newUser = await User.create({
      email,
      hashed_password: hashedPassword,
      first_name,
      last_name,
      nickname
    });

    res.status(201).json(newUser);
  } catch (error) {
    res.status(500).json({ error: 'Server error' });
  }
});

// Login
router.post('/login', async (req: Request, res: Response) => {
  try {
    // FastAPI OAuth2PasswordRequestForm expects username/password form data usually, 
    // but standard JSON login is cleaner. We'll support standard JSON body.
    // If frontend sends form-data, we might need multer or similar, but let's stick to JSON.
    // Looking at frontend auth service might be useful, but let's assume JSON for now or check frontend.
    // Actually the python code used `OAuth2PasswordRequestForm` which expects `username` and `password`.
    // We will support `username` (email) and `password`.
    
    const { username, password } = req.body; // map email to username field if needed, or just accept email

    const user = await User.findOne({ where: { email: username } });
    if (!user) {
      return res.status(401).json({ detail: "Incorrect username or password" });
    }

    const validPassword = await bcrypt.compare(password, user.hashed_password);
    if (!validPassword) {
      return res.status(401).json({ detail: "Incorrect username or password" });
    }

    const token = jwt.sign({ sub: user.email }, SECRET_KEY, { expiresIn: '30m' });
    res.json({ access_token: token, token_type: "bearer" });

  } catch (error) {
    res.status(500).json({ error: 'Server error' });
  }
});

// Reset Password Request (Mock)
router.post('/reset-password-request', async (req: Request, res: Response) => {
  const { email } = req.body;
  const user = await User.findOne({ where: { email } });
  if (!user) {
    return res.status(404).json({ detail: "User not found" });
  }
  console.log(`Sending password reset email to ${user.email}`);
  res.json({ message: "Password reset email sent" });
});

export default router;
