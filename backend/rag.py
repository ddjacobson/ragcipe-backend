import os
import glob
import constants
from rag_engine import RAGEngine # Import the new RAGEngine class
import kb_manager

# --- init RAG engine ---

print(f"{constants.BUILD} - Creating RAG Engine instance...")

if not os.path.exists(constants.VECTORSTORE_PATH) or not os.listdir(constants.VECTORSTORE_PATH):
    print(f"{constants.BUILD} - Vector store not found at '{constants.VECTORSTORE_PATH}'. Building initial store...")

    if not os.path.exists(constants.DOCS_PATH):
        os.makedirs(constants.DOCS_PATH)
        print(f"{constants.BUILD} - Created recipes directory: {constants.DOCS_PATH}")
    # Trigger the static update method
    success = kb_manager.KnowledgeBaseManager.update_kb()
    if not success:
        print("FATAL: Failed to create initial vector store. RAG Engine might not work.")


rag_engine_instance = RAGEngine()
print(f"{constants.BUILD} - RAG Engine instance created.")

def get_rag_response(user_question: str, serializable_chat_history: list, selected_recipe_filename: str | None = None):

    if not rag_engine_instance:
        print("Error: RAG Engine instance is not available.")
        return "Sorry, the recipe query engine is not initialized properly."

    return rag_engine_instance.query(user_question, serializable_chat_history, selected_recipe_filename)

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

