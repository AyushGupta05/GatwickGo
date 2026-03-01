#!/usr/bin/env bash
set -e

echo "🛫 Gatwick-GO Setup"
echo "==================="

# Check for Node.js
if ! command -v node &> /dev/null; then
  echo "❌ Node.js is not installed. Install it from https://nodejs.org/"
  exit 1
fi

echo "✅ Node.js $(node -v)"

# Install npm dependencies
echo ""
echo "📦 Installing dependencies..."
npm install

# Copy env file if it doesn't exist
if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo "✅ Created .env.local from .env.example"
else
  echo "ℹ️  .env.local already exists — skipping"
fi

echo ""
echo "✅ Setup complete! Run the app with:"
echo "   npm run dev"
