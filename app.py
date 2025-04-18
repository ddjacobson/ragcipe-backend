import os
from flask import Flask, request, jsonify, session
from flask_cors import CORS # Import CORS
from rag import get_rag_response, list_recipes # Import functions from rag.py

# Check for API key on startup

# if not os.getenv("GOOGLE_API_KEY"):
#     raise ValueError("GOOGLE_API_KEY environment variable not set. Please set it before running.")

app = Flask(__name__)
# Enable CORS for all domains on all routes, or specify origins for production
# Allows requests from your React frontend (e.g., http://localhost:3000)
CORS(app, supports_credentials=True) 

# Secret key is needed for session management
app.secret_key = os.urandom(24) 

# --- API Routes --- (Prefixed with /api)

@app.route('/') # Keep a basic root route for testing
def root():
    return jsonify({"message": "RAGcipe API is running!"})

@app.route('/api/init', methods=['GET'])
def init_chat():
    """Provides initial data for the frontend: recipes and history."""
    recipes = list_recipes()
    print(recipes)
    # Initialize chat history and selected recipe in session if not present
    if 'chat_history' not in session:
        session['chat_history'] = []
    if 'selected_recipe' not in session: # Initialize selected_recipe
        session['selected_recipe'] = None 

    return jsonify({
        'recipes': recipes,
        'chat_history': session.get('chat_history', []), # Use .get for safety
        'selected_recipe': session.get('selected_recipe', None) # Return selected recipe
    })

@app.route('/api/ask', methods=['POST'])
def ask():
    """Handles incoming questions from the user."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    user_question = data.get('question')
    selected_recipe = data.get('selected_recipe') # Get selected recipe from request

    if not user_question:
        return jsonify({"error": "Missing 'question' in request"}), 400

    # Retrieve serializable chat history from session
    chat_history = session.get('chat_history', [])

    # Get response from RAG model (updates chat_history in-place)
    # Pass the selected recipe to the RAG function
    answer = get_rag_response(user_question, chat_history, selected_recipe_filename=selected_recipe)

    # Save the updated history back to session
    session['chat_history'] = chat_history
    session.modified = True

    # Return the latest answer and the updated history
    return jsonify({
        "answer": answer, 
        "question": user_question, # Echo the question back
        "chat_history": chat_history, # Send the full updated history
        # No need to send selected_recipe back here, frontend manages its state
    })

@app.route('/api/select_recipe', methods=['POST'])
def select_recipe():
    """Sets or clears the selected recipe in the session."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.get_json()
    recipe_filename = data.get('recipe') # Can be a filename string or None/null

    # Validate? Maybe check if filename exists in list_recipes()?
    # For now, just trust the frontend.
    session['selected_recipe'] = recipe_filename
    session.modified = True
    print(f"Session selected_recipe set to: {session['selected_recipe']}") # Debugging
    return jsonify({"message": "Recipe selection updated.", "selected_recipe": recipe_filename})

@app.route('/api/clear', methods=['POST'])
def clear_history():
    """Clears the chat history and selected recipe for the current session."""
    session.pop('chat_history', None) # Use pop for safety
    session.pop('selected_recipe', None) # Also clear the selected recipe
    session.modified = True # Ensure changes are saved
    return jsonify({"message": "Chat history and recipe selection cleared."}) # Return success message

if __name__ == '__main__':
    # Port 5000 is common for Flask APIs
    app.run(host='0.0.0.0', port=5000, debug=True) 