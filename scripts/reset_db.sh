#!/bin/bash
set -e
cd "$(dirname "$0")/.."

echo "Resetting database..."
if [ -f backend/quiz.db ]; then
    rm backend/quiz.db
    echo "Removed SQLite database."
fi

echo "Running seed..."
python scripts/seed_data.py

echo "Done!"
