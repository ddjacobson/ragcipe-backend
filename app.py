import os
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import kb_manager
from werkzeug.utils import secure_filename
import json
import shutil

# Import the single RAGEngine instance from rag.py
from rag import get_rag_response, list_recipes, rag_engine_instance
# Remove direct import of update_vector_store or related things from create_vector_store
import constants # Import constants for path definitions

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
UPLOAD_FOLDER = constants.DOCS_PATH 
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


        # --- Update Vector Store on Disk --- 
        print("Triggering knowledge base update on disk...")
        # Use the static method from KnowledgeBaseManager
        # It uses paths defined in constants.py by default
        update_success = kb_manager.KnowledgeBaseManager.update_kb()

        if update_success:
            print("Knowledge base updated successfully on disk.")
            # --- Reload Vector Store in RAG Engine --- 
            print("Reloading vector store in RAG engine...")
            rag_engine_instance.reload_vectorstore() # Reload the engine's store
            
            updated_recipes = list_recipes() 
            return jsonify({
                "message": f"Recipe '{filename}' uploaded and knowledge base updated.",
                "filename": filename,
                "recipes": updated_recipes
                }), 200
        else:
            print("Knowledge base update failed after upload.")
            # Consider deleting the uploaded file if KB update fails?
            # os.remove(save_path) 
            return jsonify({"error": "File uploaded, but failed to update knowledge base"}), 500

    else:
        print(f"Upload failed: File type not allowed for '{file.filename}'")
        return jsonify({"error": "File type not allowed. Please upload a JSON file."}), 400

# --- New Remove Vector Store Endpoint ---
@app.route('/api/remove_vector_store', methods=['POST']) # Using POST for action
def remove_vector_store():
    """Removes the existing vector store directory."""
    vectorstore_path = constants.VECTORSTORE_PATH # Use path from constants
    print(f"Attempting to remove vector store at: {vectorstore_path}")
    store_existed = os.path.exists(vectorstore_path)
    try:
        if store_existed:
            shutil.rmtree(vectorstore_path)
            print(f"Vector store directory '{vectorstore_path}' removed successfully.")
        else:
             print(f"Vector store directory '{vectorstore_path}' not found. Nothing to remove.")

        # --- Reload RAG Engine's Store (even if it didn't exist) ---
        # This tells the engine to attempt loading, which will fail if the dir is gone,
        # effectively clearing its internal store.
        print("Reloading vector store in RAG engine (will clear if removed)...")
        rag_engine_instance.reload_vectorstore()

        # If the store existed and was removed, return 200 OK.
        # If it didn't exist, also return 200 OK.
        message = "Vector store removed successfully and engine reloaded." if store_existed else "Vector store not found, engine state refreshed."
        return jsonify({"message": message}), 200

    except OSError as e:
        print(f"Error removing vector store directory '{vectorstore_path}': {e}")
        # Attempt to reload engine even on error, maybe state is recoverable?
        rag_engine_instance.reload_vectorstore()
        return jsonify({"error": f"Failed to remove vector store: {e}"}), 500
    except Exception as e:
        print(f"An unexpected error occurred while removing vector store: {e}")
        rag_engine_instance.reload_vectorstore()
        return jsonify({"error": "An unexpected error occurred."}), 500

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

    # Use constant for base path
    base_path = os.path.abspath(constants.DOCS_PATH)
    target_path = os.path.abspath(os.path.join(base_path, filename_to_remove))

    # Security check
    if not target_path.startswith(base_path + os.sep) or not os.path.basename(target_path) == filename_to_remove:
         print(f"Attempt to access file outside designated folder rejected: {filename_to_remove}")
         return jsonify({"error": "Invalid filename or path"}), 400

    print(f"Attempting to remove recipe file: {target_path}")
    file_existed = os.path.exists(target_path)

    try:
        if file_existed:
            os.remove(target_path)
            print(f"Recipe file '{filename_to_remove}' removed successfully.")
        else:
             print(f"Recipe file '{filename_to_remove}' not found at '{target_path}'.")

        # --- Update Vector Store on Disk (regardless of whether file existed) --- 
        # This ensures consistency if the file was somehow deleted externally.
        print("Triggering knowledge base update on disk after removal attempt...")
        update_success = kb_manager.KnowledgeBaseManager.update_kb()

        if update_success:
            print("Knowledge base updated successfully on disk.")
            # --- Reload Vector Store in RAG Engine --- 
            print("Reloading vector store in RAG engine...")
            rag_engine_instance.reload_vectorstore()
            
            updated_recipes = list_recipes()
            cleared_selection = False
            if session.get('selected_recipe') == filename_to_remove:
                 session['selected_recipe'] = None
                 session.modified = True
                 cleared_selection = True
            
            status_code = 200 if file_existed else 404 # OK if removed, Not Found if it wasn't there
            message = f"Recipe '{filename_to_remove}' processed. Knowledge base updated." 
            if not file_existed: message += " (File was not found)."
                
            return jsonify({
                "message": message,
                "recipes": updated_recipes,
                "cleared_selection": cleared_selection
                }), status_code
        else:
            print("Knowledge base update failed after recipe removal attempt.")
             # Even if KB update fails, try to reload the engine with whatever is on disk currently
            print("Attempting to reload RAG engine with potentially stale index...")
            rag_engine_instance.reload_vectorstore() 
            # Report error, but the file might be gone and index stale
            error_message = "Recipe file processed, but failed to update knowledge base. Index may be inconsistent."
            if not file_existed: error_message = "Recipe file not found, and failed to update knowledge base."
            return jsonify({"error": error_message}), 500

    except OSError as e:
        print(f"Error removing recipe file '{target_path}': {e}")
        # Attempt KB update and engine reload even on file removal error
        kb_manager.KnowledgeBaseManager.update_kb() 
        rag_engine_instance.reload_vectorstore()
        return jsonify({"error": f"Failed to remove recipe file: {e}"}), 500
    except Exception as e:
        print(f"An unexpected error occurred during recipe removal: {e}")
        # Attempt KB update and engine reload even on other errors
        kb_manager.KnowledgeBaseManager.update_kb() 
        rag_engine_instance.reload_vectorstore()
        return jsonify({"error": "An unexpected error occurred during recipe removal."}), 500

if __name__ == '__main__':
    # Ensure the recipes directory exists on startup
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        print(f"Created recipes directory at '{UPLOAD_FOLDER}' on startup.")
    # Port 5000 is common for Flask APIs
    app.run(host='0.0.0.0', port=5000, debug=True) 