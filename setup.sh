#!/bin/bash

echo "📂 Navigating to backend folder..."
cd backend || { echo "❌ backend directory not found!"; exit 1; }

echo "🔧 Creating Python virtual environment..."
python3 -m venv venv

echo "📦 Activating virtual environment and installing backend dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install flask flask-socketio eventlet

echo "✅ Backend setup complete!"
cd ..

echo "📂 Navigating to frontend folder..."
cd frontend || { echo "❌ frontend directory not found!"; exit 1; }

echo "⬇️ Installing frontend (React/Vite) dependencies..."
npm install

echo "✅ Frontend setup complete!"

echo "🎉 All done!"
echo "👉 To run backend:"
echo "   cd backend && source venv/bin/activate && python app.py"
echo "👉 To run frontend:"
echo "   cd frontend && npm run dev"
