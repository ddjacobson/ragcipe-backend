import os
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import json
import shutil # Import shutil

# Import functions from rag.py and create_vector_store.py
from rag import get_rag_response, list_recipes
from create_vector_store import update_vector_store, DOCS_PATH, VECTORSTORE_PATH # Import VECTORSTORE_PATH

# Check for API key on startup

# if not os.getenv("GOOGLE_API_KEY"):
#     raise ValueError("GOOGLE_API_KEY environment variable not set. Please set it before running.")

app = Flask(__name__)
# Enable CORS for all domains on all routes, or specify origins for production
# Allows requests from your React frontend (e.g., http://localhost:3000)
CORS(app, supports_credentials=True) 

# Secret key is needed for session management
app.secret_key = os.urandom(24) 

# --- Configuration ---
# Define the upload folder relative to the app's root
UPLOAD_FOLDER = DOCS_PATH 
# Define allowed file extensions
ALLOWED_EXTENSIONS = {'json'} 

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Optional: Limit file size (e.g., 16MB)

# --- Helper Function ---
def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- API Routes --- (Prefixed with /api)

@app.route('/') # Keep a basic root route for testing
def root():
    return jsonify({"message": "RAGcipe API is running!"})

@app.route('/api/init', methods=['GET'])
def init_chat():
    """Provides initial data for the frontend: recipes and history."""
    recipes = list_recipes()
    print(f"Initializing chat. Recipes found: {recipes}") # Debugging
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

# --- New Upload Endpoint ---
@app.route('/api/upload_recipe', methods=['POST'])
def upload_recipe():
    """Handles recipe file uploads."""
    if 'recipeFile' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['recipeFile']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename) # Sanitize filename
        # Ensure the upload folder exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
             os.makedirs(app.config['UPLOAD_FOLDER'])
             print(f"Created upload directory: {app.config['UPLOAD_FOLDER']}")

        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Basic JSON validation before saving (optional but recommended)
        try:
            # Read content without saving first
            content = file.read().decode('utf-8') 
            json.loads(content) # Try parsing
            # If parsing works, save the content
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"File '{filename}' saved successfully to '{save_path}'.")
        except json.JSONDecodeError:
             print(f"Error: Uploaded file '{filename}' is not valid JSON.")
             return jsonify({"error": "Invalid JSON file content"}), 400
        except Exception as e:
            print(f"Error saving file '{filename}': {e}")
            return jsonify({"error": "Failed to save file"}), 500
        finally:
             # Reset file pointer if you need to read it again (usually not needed here)
             file.seek(0) 
             print("seeking file")


        # --- Update Vector Store ---
        print("Triggering vector store update...")
        update_success = update_vector_store() # Call the refactored function
        
        if update_success:
            print("Vector store updated successfully after upload.")
             # Also update the list of recipes for the frontend
            updated_recipes = list_recipes() 

            # add in logic where we restart the server

            return jsonify({
                "message": f"Recipe '{filename}' uploaded and vector store updated.",
                "filename": filename,
                "recipes": updated_recipes # Send back the new list
                }), 200
        else:
            print("Vector store update failed after upload.")
            # Consider deleting the uploaded file if the update fails?
            # os.remove(save_path) 
            return jsonify({"error": "File uploaded, but failed to update vector store"}), 500

    else:
        print(f"Upload failed: File type not allowed for '{file.filename}'")
        return jsonify({"error": "File type not allowed. Please upload a JSON file."}), 400

# --- New Remove Vector Store Endpoint ---
@app.route('/api/remove_vector_store', methods=['POST']) # Using POST for action
def remove_vector_store():
    """Removes the existing vector store directory."""
    print(f"Attempting to remove vector store at: {VECTORSTORE_PATH}")
    if os.path.exists(VECTORSTORE_PATH):
        try:
            shutil.rmtree(VECTORSTORE_PATH)
            print(f"Vector store directory '{VECTORSTORE_PATH}' removed successfully.")
            # Optionally, clear the session's selected recipe if the store is gone?
            # session.pop('selected_recipe', None)
            # session.modified = True
            return jsonify({"message": "Vector store removed successfully."}), 200
        except OSError as e:
            print(f"Error removing vector store directory '{VECTORSTORE_PATH}': {e}")
            return jsonify({"error": f"Failed to remove vector store: {e}"}), 500
        except Exception as e:
            print(f"An unexpected error occurred while removing vector store: {e}")
            return jsonify({"error": "An unexpected error occurred."}), 500
    else:
        print(f"Vector store directory '{VECTORSTORE_PATH}' not found. Nothing to remove.")
        return jsonify({"message": "Vector store not found. Nothing to remove."}), 200 # It's not an error if it's already gone

# --- New Remove Single Recipe Endpoint ---
@app.route('/api/remove_recipe', methods=['POST'])
def remove_recipe():
    """Removes a specific recipe file and updates the vector store."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    filename_to_remove = data.get('filename')

    if not filename_to_remove:
        return jsonify({"error": "Missing 'filename' in request body"}), 400

    # Basic security check: Ensure filename doesn't try to escape the UPLOAD_FOLDER
    # secure_filename might change the name, so we do a path join and check instead
    target_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], filename_to_remove))
    base_path = os.path.abspath(app.config['UPLOAD_FOLDER'])

    # Prevent path traversal (e.g., ../../etc/passwd)
    if not target_path.startswith(base_path + os.sep) or not os.path.basename(target_path) == filename_to_remove:
         print(f"Attempt to access file outside designated folder rejected: {filename_to_remove}")
         return jsonify({"error": "Invalid filename or path"}), 400

    print(f"Attempting to remove recipe file: {target_path}")

    if os.path.exists(target_path):
        try:
            os.remove(target_path)
            print(f"Recipe file '{filename_to_remove}' removed successfully.")

            # --- Update Vector Store ---
            print("Triggering vector store update after file removal...")
            update_success = update_vector_store() # Rebuild the index

            if update_success:
                print("Vector store updated successfully after recipe removal.")
                # Also update the list of recipes for the frontend
                updated_recipes = list_recipes()
                # If the removed recipe was the selected one, clear the selection
                if session.get('selected_recipe') == filename_to_remove:
                     session['selected_recipe'] = None
                     session.modified = True
                return jsonify({
                    "message": f"Recipe '{filename_to_remove}' removed and vector store updated.",
                    "recipes": updated_recipes, # Send back the new list
                    "cleared_selection": session.get('selected_recipe') is None # Indicate if selection was cleared
                    }), 200
            else:
                print("Vector store update failed after recipe removal.")
                 # This is tricky - the file is gone, but the index is stale. 
                 # Maybe try to restore the file? For now, just report the error.
                return jsonify({"error": "Recipe file removed, but failed to update vector store. Index may be inconsistent."}), 500

        except OSError as e:
            print(f"Error removing recipe file '{target_path}': {e}")
            return jsonify({"error": f"Failed to remove recipe file: {e}"}), 500
        except Exception as e:
            print(f"An unexpected error occurred during recipe removal: {e}")
            return jsonify({"error": "An unexpected error occurred during recipe removal."}), 500
    else:
        print(f"Recipe file '{filename_to_remove}' not found at '{target_path}'.")
        # Also trigger vector store update if file not found, in case index is inconsistent
        update_vector_store() 
        updated_recipes = list_recipes()
        return jsonify({
                "message": f"Recipe '{filename_to_remove}' not found. Vector store possibly resynced.", 
                "recipes": updated_recipes
                }), 404 # Not Found

if __name__ == '__main__':
    # Ensure the recipes directory exists on startup
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        print(f"Created recipes directory at '{UPLOAD_FOLDER}' on startup.")
    # Port 5000 is common for Flask APIs
    app.run(host='0.0.0.0', port=5000, debug=True) 