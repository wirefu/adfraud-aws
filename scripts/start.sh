#!/bin/bash
# Start Fraud Analytics Dashboard

echo "🛡️  Starting FraudGuard AI Dashboard..."
echo ""

# Check if dependencies are installed
if ! python -c "import streamlit" 2>/dev/null; then
    echo "❌ Streamlit not found. Installing dependencies..."
    pip install -q -r requirements.txt
fi

# Start dashboard
echo "✅ Starting dashboard on http://localhost:8501"
echo "   Press Ctrl+C to stop"
echo ""

cd "$(dirname "$0")"
streamlit run app.py --server.port=8501

