#!/bin/bash
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

set -e

echo "Building Frontend..."
cd frontend
npm install
npm run build
cd ..

echo "Setting up Server..."
cd server
npm install
npm run build

echo "Starting Unified App..."
echo "Access the app at http://localhost:8080"
# Run the built server
npm start
