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


import { DataTypes, Model, Optional } from 'sequelize';
import { sequelize } from '../database';

// --- Interfaces ---

interface UserAttributes {
  id: number;
  email: string;
  hashed_password: string;
  first_name: string;
  last_name: string;
  nickname: string;
  profile_picture_url?: string;
}

interface UserCreationAttributes extends Optional<UserAttributes, 'id'> {}

interface EventAttributes {
  id: number;
  title: string;
  description: string;
  start_time: Date;
  distance: number;
  unit: string;
  owner_id: number;
}

interface EventCreationAttributes extends Optional<EventAttributes, 'id'> {}

interface RSVPAttributes {
  id: number;
  user_id: number;
  event_id: number;
}
interface RSVPCreationAttributes extends Optional<RSVPAttributes, 'id'> {}

interface VoteAttributes {
  id: number;
  user_id: number;
  event_id: number;
}
interface VoteCreationAttributes extends Optional<VoteAttributes, 'id'> {}

interface RatingAttributes {
  id: number;
  value: number;
  user_id: number;
  event_id: number;
}
interface RatingCreationAttributes extends Optional<RatingAttributes, 'id'> {}

interface MessageAttributes {
  id: number;
  content: string;
  owner_id: number;
  created_at?: Date;
}
interface MessageCreationAttributes extends Optional<MessageAttributes, 'id'> {}

// --- Models ---

export class User extends Model<UserAttributes, UserCreationAttributes> implements UserAttributes {
  public id!: number;
  public email!: string;
  public hashed_password!: string;
  public first_name!: string;
  public last_name!: string;
  public nickname!: string;
  public profile_picture_url?: string;
}

User.init({
  id: {
    type: DataTypes.INTEGER,
    autoIncrement: true,
    primaryKey: true,
  },
  email: {
    type: DataTypes.STRING,
    allowNull: false,
    unique: true,
  },
  hashed_password: {
    type: DataTypes.STRING,
    allowNull: false,
  },
  first_name: {
    type: DataTypes.STRING,
    allowNull: false,
  },
  last_name: {
    type: DataTypes.STRING,
    allowNull: false,
  },
  nickname: {
    type: DataTypes.STRING,
    allowNull: false,
  },
  profile_picture_url: {
    type: DataTypes.STRING,
    allowNull: true
  }
}, {
  sequelize,
  tableName: 'users',
  timestamps: false, // Python version didn't have updated_at/created_at on users explicitly in the snippet
});

export class Event extends Model<EventAttributes, EventCreationAttributes> implements EventAttributes {
  public id!: number;
  public title!: string;
  public description!: string;
  public start_time!: Date;
  public distance!: number;
  public unit!: string;
  public owner_id!: number;
  public votes?: Vote[];
}

Event.init({
  id: {
    type: DataTypes.INTEGER,
    autoIncrement: true,
    primaryKey: true,
  },
  title: {
    type: DataTypes.STRING,
    allowNull: false,
  },
  description: {
    type: DataTypes.STRING,
    allowNull: false,
  },
  start_time: {
    type: DataTypes.DATE,
    defaultValue: DataTypes.NOW,
  },
  distance: {
    type: DataTypes.FLOAT,
    allowNull: false,
  },
  unit: {
    type: DataTypes.STRING,
    allowNull: false,
  },
  owner_id: {
    type: DataTypes.INTEGER,
    allowNull: false,
  },
}, {
  sequelize,
  tableName: 'events',
  timestamps: false,
});

export class RSVP extends Model<RSVPAttributes, RSVPCreationAttributes> implements RSVPAttributes {
  public id!: number;
  public user_id!: number;
  public event_id!: number;
}

RSVP.init({
  id: {
    type: DataTypes.INTEGER,
    autoIncrement: true,
    primaryKey: true,
  },
  user_id: {
    type: DataTypes.INTEGER,
    allowNull: false,
  },
  event_id: {
    type: DataTypes.INTEGER,
    allowNull: false,
  },
}, {
  sequelize,
  tableName: 'rsvps',
  timestamps: false,
});

export class Vote extends Model<VoteAttributes, VoteCreationAttributes> implements VoteAttributes {
  public id!: number;
  public user_id!: number;
  public event_id!: number;
}

Vote.init({
  id: {
    type: DataTypes.INTEGER,
    autoIncrement: true,
    primaryKey: true,
  },
  user_id: {
    type: DataTypes.INTEGER,
    allowNull: false,
  },
  event_id: {
    type: DataTypes.INTEGER,
    allowNull: false,
  },
}, {
  sequelize,
  tableName: 'votes',
  timestamps: false,
});

export class Rating extends Model<RatingAttributes, RatingCreationAttributes> implements RatingAttributes {
  public id!: number;
  public value!: number;
  public user_id!: number;
  public event_id!: number;
}

Rating.init({
  id: {
    type: DataTypes.INTEGER,
    autoIncrement: true,
    primaryKey: true,
  },
  value: {
    type: DataTypes.INTEGER,
    allowNull: false,
  },
  user_id: {
    type: DataTypes.INTEGER,
    allowNull: false,
  },
  event_id: {
    type: DataTypes.INTEGER,
    allowNull: false,
  },
}, {
  sequelize,
  tableName: 'ratings',
  timestamps: false,
});

export class Message extends Model<MessageAttributes, MessageCreationAttributes> implements MessageAttributes {
  public id!: number;
  public content!: string;
  public owner_id!: number;
  public created_at!: Date;
  public owner?: User; // Include for association typing
}

Message.init({
  id: {
    type: DataTypes.INTEGER,
    autoIncrement: true,
    primaryKey: true,
  },
  content: {
    type: DataTypes.STRING,
    allowNull: false,
  },
  owner_id: {
    type: DataTypes.INTEGER,
    allowNull: false,
  },
  created_at: {
    type: DataTypes.DATE,
    defaultValue: DataTypes.NOW,
  },
}, {
  sequelize,
  tableName: 'messages',
  timestamps: false,
});

// --- Associations ---

User.hasMany(Event, { foreignKey: 'owner_id', as: 'events' });
Event.belongsTo(User, { foreignKey: 'owner_id', as: 'owner' });

User.hasMany(RSVP, { foreignKey: 'user_id', as: 'rsvps' });
RSVP.belongsTo(User, { foreignKey: 'user_id', as: 'user' });
Event.hasMany(RSVP, { foreignKey: 'event_id', as: 'rsvps' });
RSVP.belongsTo(Event, { foreignKey: 'event_id', as: 'event' });

User.hasMany(Vote, { foreignKey: 'user_id', as: 'votes' });
Vote.belongsTo(User, { foreignKey: 'user_id', as: 'user' });
Event.hasMany(Vote, { foreignKey: 'event_id', as: 'votes' });
Vote.belongsTo(Event, { foreignKey: 'event_id', as: 'event' });

User.hasMany(Rating, { foreignKey: 'user_id', as: 'ratings' });
Rating.belongsTo(User, { foreignKey: 'user_id', as: 'user' });
Event.hasMany(Rating, { foreignKey: 'event_id', as: 'ratings' });
Rating.belongsTo(Event, { foreignKey: 'event_id', as: 'event' });

User.hasMany(Message, { foreignKey: 'owner_id', as: 'messages' });
Message.belongsTo(User, { foreignKey: 'owner_id', as: 'owner' });

