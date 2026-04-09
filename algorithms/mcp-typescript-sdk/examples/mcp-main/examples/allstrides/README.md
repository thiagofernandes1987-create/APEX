# AllStrides: Google remote MCP for Cloud SQL and Developer Knowledge

[![Google Cloud](https://img.shields.io/badge/Blog-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white)](https://cloud.google.com/blog/products/ai-machine-learning/announcing-official-mcp-support-for-google-services)
[![Codelab](https://img.shields.io/badge/Codelab-58A55d.svg?style=for-the-badge&logo=devbox&logoColor=white)](https://codelabs.developers.google.com/ai-mcp-dk-csql#0)
[![Screencast](https://img.shields.io/badge/Screencast-%23FF0000.svg?style=for-the-badge&logo=YouTube&logoColor=white)](https://youtu.be/SeuhYVg8-AU?si=uGQHyU4N_vZoZBUn)

This directory contains the data artifacts and infrastructure setup scripts for the **Google remote MCP for Cloud SQL and Developer Knowledge** demo.  

## Demo Overview

This scenario demonstrates an AI Agent's ability to act as a Product Architect, migrating a localized application to the cloud using Google Model Context Protocol (MCP) servers. By equipping Gemini CLI with access to Cloud SQL, Developer Knowledge and Cloud Run MCP, you can transform a manual deployment process into an agentic orchestration.

> **"How do I evolve AllStrides from a local-only prototype into a secure, globally accessible enterprise platform?"**

Gemini CLI interacts with the Google Cloud ecosystem by leveraging three specific MCP servers to modernize the stack:

1.  **Developer Knowledge MCP**: To analyze the current application structure and identify the optimal Google Cloud database.
2.  **Cloud SQL MCP**: To provision a production-grade database instance and migrate local fitness community data to the cloud via a single natural language prompt.
3.  **Cloud Run MCP**: To containerize the allstrides application and deploy it to a serverless environment, making AllStrides live and accessible to users worldwide.

### Architecture Diagram

<img width="941" height="439" alt="Developer-knowledge-mcp-cloudsql-mcp-cloudrun-mcp" src="https://github.com/user-attachments/assets/cbbc8785-41c5-4e1c-87c5-bae1bfa77f5e" />


This directory contains the sample application artifacts and a lab demonstrating how the MCP support for Developer Knowledge, Databases ad Cloud Run help to migrate demo application to the cloud.
## Sample Application
The sample "Allstrides" application is featuring event management, fuser authentication, profile management, event CRUD operations, RSVP functionality, and real-time chat.

## Architecture

This project is a **Unified Full-Stack TypeScript Application**.
- **Frontend**: React (TypeScript)
- **Backend**: Node.js / Express (TypeScript)
- **Database**: SQLite (managed by Sequelize)
- **Real-time**: WebSocket (ws)
- **Deployment**: Single container serving both API and Static Frontend assets.

### Project Structure
```text
Listing: allstrides
├── frontend/
│   ├── public/
│   └── src/
│       ├── components/
│       │   ├── chat/
│       │   └── layout/
│       └── pages/
│           ├── auth/
│           ├── events/
│           └── profile/
└── server/
    └── src/
        ├── middleware/
        ├── models/
        └── routes/
```

- `frontend/`: React application (CRA).
- `server/`: Node.js/Express API and WebSocket server.
- `docker-compose.yml`: Local deployment config.
- `start_allstrides.sh`: Helper script for local execution.

## Getting Started

### Prerequisites

- Node.js (v22 or later)
- Docker (optional)

### Configuration

The application listens on port `8080` by default. You can change this using:
1.  **Environment Variable:** `PORT=3000 npm start`
2.  **Command Line Argument:** `npm start -- --port 3000`

### Running Locally

1.  **Use the Helper Script:**
    This script builds the frontend, sets up the server, and starts the application.
    ```bash
    ./start_allstrides.sh
    ```
    The application will be available at [http://localhost:8080](http://localhost:8080).

2.  **Manual Setup:**
    
    *Build Frontend:*
    ```bash
    cd frontend
    npm install
    npm run build
    cd ..
    ```

    *Start Server:*
    ```bash
    cd server
    npm install
    npm run build
    npm start
    ```

### Running with Docker

1.  Start the application:
    ```bash
    docker compose up --build
    ```
    The application will be available at [http://localhost:8080](http://localhost:8080).

2.  Stop the application:
    ```bash
    docker compose down
    ```

### Seeding the Database

You can populate the database with random test data using two methods:

**Method 1: Scripted Seeding (Internal)**
To use the internal Sequelize seed script (50 users, 200 events, 100 messages):
```bash
cd server
npm run seed
```

**Method 2: SQL Import (External)**
To import the pre-generated SQLite script (50 users, 100 events from 2025-2026, 150 messages, and votes):
```bash
# From the root of the 'allstrides' folder
sqlite3 allstrides.db < seed_data.sql
```
*Note: This will overwrite existing data for users, events, messages, and votes.*

## Development Notes

- **Database**: The application uses a local SQLite database (`allstrides.db`) located in the root `allstrides` folder (when running locally) or mapped to the container volume.
- **Authentication**: Uses JWT. Passwords are hashed with BCrypt.
- **API Documentation**: The backend endpoints are available at `/api/...`.
- **Frontend Routing**: The server is configured to handle client-side routing (SPA) by falling back to `index.html` for non-API routes.

## License
This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) file for details.
