#
# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This program was created with help of Gemini CLI
#

import random
from datetime import datetime, timedelta

# Configuration
NUM_USERS = 50
NUM_EVENTS = 100
NUM_MESSAGES = 150
DATE_START = datetime(2025, 11, 1)
DATE_END = datetime(2026, 11, 30)

first_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Hannah", "Isaac", "Jack", "Kathy", "Liam", "Mia", "Noah", "Olivia", "Paul", "Quinn", "Ryan", "Sophia", "Thomas", "Umar", "Victor", "Wendy", "Xavier", "Yara", "Zane"]
last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
event_adjectives = ["Morning", "Evening", "Weekend", "Charity", "Marathon", "Sprint", "Trail", "City", "Park", "Mountain", "Sunny", "Cloudy", "Forest", "Beach"]
event_types = ["Run", "Jog", "Walk", "Hike", "Race", "Dash", "Stroll", "Trot", "Climb"]

# Pre-hashed 'password123'
HASHED_PASSWORD = "$2a$10$76.m1H/3G9nO.k1k.k1k.k1k.k1k.k1k.k1k.k1k.k1k.k1k.k1k.k"

def random_date(start, end):
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = random.randrange(int_delta)
    return start + timedelta(seconds=random_second)

def generate_sql():
    sql = []
    
    # Clear existing data (optional but recommended for a clean seed)
    sql.append("DELETE FROM votes;")
    sql.append("DELETE FROM ratings;")
    sql.append("DELETE FROM rsvps;")
    sql.append("DELETE FROM messages;")
    sql.append("DELETE FROM events;")
    sql.append("DELETE FROM users;")
    
    # 1. Users
    print(f"Generating {NUM_USERS} users...")
    for i in range(1, NUM_USERS + 1):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        email = f"user{i}@example.com"
        nickname = f"{fn.lower()}{ln.lower()}{i}"
        sql.append(f"INSERT INTO users (id, email, hashed_password, first_name, last_name, nickname, profile_picture_url) VALUES ({i}, '{email}', '{HASHED_PASSWORD}', '{fn}', '{ln}', '{nickname}', 'https://i.pravatar.cc/150?u={i}');")

    # 2. Events
    print(f"Generating {NUM_EVENTS} events...")
    for i in range(1, NUM_EVENTS + 1):
        owner_id = random.randint(1, NUM_USERS)
        title = f"{random.choice(event_adjectives)} {random.choice(event_types)} {i}"
        description = "Join us for a wonderful event. All levels welcome!"
        date = random_date(DATE_START, DATE_END).strftime('%Y-%m-%d %H:%M:%S')
        distance = random.randint(1, 42)
        unit = random.choice(['km', 'mi'])
        sql.append(f"INSERT INTO events (id, title, description, start_time, distance, unit, owner_id) VALUES ({i}, '{title}', '{description}', '{date}', {distance}, '{unit}', {owner_id});")

    # 3. Messages
    print(f"Generating {NUM_MESSAGES} messages...")
    for i in range(1, NUM_MESSAGES + 1):
        owner_id = random.randint(1, NUM_USERS)
        content = f"Message {i}: Looking forward to the next run! Who else is in?"
        # Messages from some time in late 2025 onwards
        date = random_date(datetime(2025, 1, 1), datetime(2025, 12, 31)).strftime('%Y-%m-%d %H:%M:%S')
        sql.append(f"INSERT INTO messages (id, content, owner_id, created_at) VALUES ({i}, '{content}', {owner_id}, '{date}');")

    # 4. Votes
    print("Generating random votes...")
    vote_id = 1
    for event_id in range(1, NUM_EVENTS + 1):
        # Each event gets between 0 and 15 votes
        num_votes = random.randint(0, 15)
        voters = random.sample(range(1, NUM_USERS + 1), num_votes)
        for voter_id in voters:
            sql.append(f"INSERT INTO votes (id, user_id, event_id) VALUES ({vote_id}, {voter_id}, {event_id});")
            vote_id += 1

    return "\n".join(sql)

if __name__ == "__main__":
    content = generate_sql()
    with open("allstrides/seed_data.sql", "w") as f:
        f.write(content)
    print("Successfully generated allstrides/seed_data.sql")