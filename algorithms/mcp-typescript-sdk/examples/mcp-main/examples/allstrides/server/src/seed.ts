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


import { sequelize, connectDB } from './database';
import { User, Event, Message, Vote, Rating, RSVP } from './models';
import bcrypt from 'bcryptjs';

const NUM_USERS = 50;
const NUM_EVENTS = 200;
const NUM_MESSAGES = 100;

const firstNames = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Hannah", "Isaac", "Jack", "Kathy", "Liam", "Mia", "Noah", "Olivia", "Paul", "Quinn", "Ryan", "Sophia", "Thomas"];
const lastNames = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson"];
const eventAdjectives = ["Morning", "Evening", "Weekend", "Charity", "Marathon", "Sprint", "Trail", "City", "Park", "Mountain"];
const eventTypes = ["Run", "Jog", "Walk", "Hike", "Race", "Dash", "Stroll"];

const getRandom = (arr: any[]) => arr[Math.floor(Math.random() * arr.length)];
const getRandomInt = (min: number, max: number) => Math.floor(Math.random() * (max - min + 1)) + min;
const getRandomDate = (start: Date, end: Date) => new Date(start.getTime() + Math.random() * (end.getTime() - start.getTime()));

async function seed() {
  await connectDB();
  console.log('Database connected. Starting seed...');

  // 1. Create Users
  console.log(`Creating ${NUM_USERS} users...`);
  const users: User[] = [];
  const hashedPassword = await bcrypt.hash('password123', 10);

  for (let i = 0; i < NUM_USERS; i++) {
    const fn = getRandom(firstNames);
    const ln = getRandom(lastNames);
    try {
      const user = await User.create({
        email: `user${i}@example.com`,
        hashed_password: hashedPassword,
        first_name: fn,
        last_name: ln,
        nickname: `${fn}${ln}${i}`,
        profile_picture_url: `https://i.pravatar.cc/150?u=${i}`
      });
      users.push(user);
    } catch (e) {
      console.log(`Skipping user creation for user${i} (might exist)`);
    }
  }
  
  // Re-fetch all users to ensure we have them if we skipped creation
  const allUsers = await User.findAll();
  if (allUsers.length === 0) {
      console.error("No users found. Aborting.");
      return;
  }

  // 2. Create Events
  console.log(`Creating ${NUM_EVENTS} events...`);
  const events: Event[] = [];
  for (let i = 0; i < NUM_EVENTS; i++) {
    const owner = getRandom(allUsers);
    const event = await Event.create({
      title: `${getRandom(eventAdjectives)} ${getRandom(eventTypes)} ${i}`,
      description: "Join us for a wonderful event. All levels welcome!",
      start_time: getRandomDate(new Date(), new Date(Date.now() + 90 * 24 * 60 * 60 * 1000)), // Next 90 days
      distance: getRandomInt(1, 42),
      unit: Math.random() > 0.5 ? 'km' : 'mi',
      owner_id: owner.id
    });
    events.push(event);
  }

  // 3. Create Messages
  console.log(`Creating ${NUM_MESSAGES} chat messages...`);
  for (let i = 0; i < NUM_MESSAGES; i++) {
    const user = getRandom(allUsers);
    await Message.create({
      content: `Hey everyone! This is message number ${i}. Who is running this weekend?`,
      owner_id: user.id,
      created_at: getRandomDate(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000), new Date()) // Last 7 days
    });
  }

  // 4. Create Votes (Randomly)
  console.log('Populating votes...');
  for (const event of events) {
    // Random number of votes (0 to 10) for each event
    const numVotes = getRandomInt(0, 10);
    const shuffledUsers = [...allUsers].sort(() => 0.5 - Math.random());
    const voters = shuffledUsers.slice(0, numVotes);

    for (const voter of voters) {
      await Vote.create({
        user_id: voter.id,
        event_id: event.id
      });
    }
  }

  console.log('Seeding complete!');
  process.exit(0);
}

seed().catch(err => {
  console.error('Seeding failed:', err);
  process.exit(1);
});
