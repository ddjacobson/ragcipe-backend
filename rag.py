import os
import glob
import constants
from rag_engine import RAGEngine # Import the new RAGEngine class

# --- Initialize the RAG Engine --- 
# Create a single instance for the application lifecycle
print("Creating RAG Engine instance...")
# Ensure the vector store is built if it doesn't exist before creating the engine
if not os.path.exists(constants.VECTORSTORE_PATH) or not os.listdir(constants.VECTORSTORE_PATH):
    print(f"Vector store not found at '{constants.VECTORSTORE_PATH}'. Building initial store...")
    # Import kb_manager here only if needed for initial build
    import kb_manager
    if not os.path.exists(constants.DOCS_PATH):
        os.makedirs(constants.DOCS_PATH)
        print(f"Created recipes directory: {constants.DOCS_PATH}")
    # Trigger the static update method
    success = kb_manager.KnowledgeBaseManager.update_kb()
    if not success:
        print("FATAL: Failed to create initial vector store. RAG Engine might not work.")
        # Decide how to handle this - maybe raise an exception?
        # For now, we'll let the engine initialization proceed, it will likely fail to load.

rag_engine_instance = RAGEngine()
print("RAG Engine instance created.")

# --- Function to get RAG response --- 
# This function now acts as a wrapper around the RAGEngine instance's query method
def get_rag_response(user_question: str, serializable_chat_history: list, selected_recipe_filename: str | None = None):
    """
    Invokes the RAG engine with the given question and chat history.
    Updates history in a serializable format (list of dictionaries).
    Optionally uses the context of a selected recipe filename.
    """
    if not rag_engine_instance:
        print("Error: RAG Engine instance is not available.")
        return "Sorry, the recipe query engine is not initialized properly."
        
    # Delegate the query to the RAGEngine instance
    # The engine's query method now handles history transformation and RAG chain invocation
    return rag_engine_instance.query(user_question, serializable_chat_history, selected_recipe_filename)

# --- Function to list recipe files --- 
# This function remains unchanged
def list_recipes():
    """Lists the recipe files in the DOCS_PATH directory."""
    try:
        if not os.path.exists(constants.DOCS_PATH):
             print(f"Recipes directory '{constants.DOCS_PATH}' not found. Returning empty list.")
             return []
        recipe_files = glob.glob(os.path.join(constants.DOCS_PATH, "*.json"))
        return [os.path.basename(f) for f in recipe_files]
    except Exception as e:
        print(f"Error listing recipes: {e}")
        return []

