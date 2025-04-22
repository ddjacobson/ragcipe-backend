import shutil
import os
import json

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings # type: ignore
import constants # Import constants

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# --- Helper function moved outside the class ---
def format_recipe(recipe):
    """Formats the recipe JSON data into a string for embedding."""
    name = recipe.get("name", "")
    desc = recipe.get("description", "")
    steps = "\n".join(step["instruction"] for step in recipe.get("steps", []))
    ingredients_str = ""

    for step in recipe.get("steps", []):
        ing = step.get("ingredients", [])
        for ingredient_item in ing:
            ingredients_str += ingredient_item.get("food", {}).get("name", "") + " : " + str(ingredient_item.get("amount", "")) + " "
            if ingredient_item.get("unit", {}):
                ingredients_str += ingredient_item.get("unit", {}).get("name", "") + "\n"
            else:
                ingredients_str += "\n"

    return f"Recipe: {name}\n\nDescription:\n{desc}\n\nIngredients:\n{ingredients_str}\n\nSteps:\n{steps}"

class KnowledgeBaseManager:
    # On-disk knowledge base manager

    def __init__(self):
        # Initialization logic might not be needed if only using static/class methods
        pass

    @staticmethod
    def update_kb(kb_path=constants.VECTORSTORE_PATH, ground_truth_path=constants.DOCS_PATH) -> bool:
        """Reads all JSON recipes, creates embeddings, and saves/overwrites the vector store on disk."""
        print(f"Starting vector store update process for path: {kb_path}")
        # Consider removing the existing store first if overwriting is intended
        if os.path.exists(kb_path):
            try:
                shutil.rmtree(kb_path)
                print(f"Removed existing vector store at '{kb_path}' before update.")
            except OSError as e:
                print(f"Error removing existing vector store at '{kb_path}': {e}")
                # Decide if this should be a fatal error (return False) or just a warning
                # return False # Uncomment if removal failure should stop the update

        documents = []
        try:
            if not os.path.exists(ground_truth_path):
                os.makedirs(ground_truth_path)
                print(f"Created recipes directory at '{ground_truth_path}'")

            recipe_files = [f for f in os.listdir(ground_truth_path) if f.endswith('.json')]
            print(f"Found {len(recipe_files)} recipe files in '{ground_truth_path}'.")

            for recipe_file in recipe_files:
                recipe_path = os.path.join(ground_truth_path, recipe_file)
                try:
                    with open(recipe_path, 'r', encoding='utf-8') as f: # Specify encoding
                        data = json.load(f)
                    # Use the standalone format_recipe function
                    doc_text = format_recipe(data)
                    documents.append(Document(page_content=doc_text, metadata={"source": recipe_file}))
                except json.JSONDecodeError:
                    print(f"Warning: Skipping invalid JSON file: {recipe_file}")
                except Exception as e:
                    print(f"Warning: Error processing file {recipe_file}: {e}")

            if not documents:
                print("No valid documents found. Vector store will not be created/updated.")
                # Ensure an empty directory exists if needed by downstream loaders
                if not os.path.exists(kb_path):
                    os.makedirs(kb_path)
                # Or handle the case where no vector store exists gracefully later
                return True # Successful in the sense that there was nothing to do

            print(f"Processing {len(documents)} documents for vector store.")
            embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
            vectorstore = FAISS.from_documents(documents, embeddings)
            vectorstore.save_local(kb_path)
            print(f"Vector store successfully created/updated at '{kb_path}'.")
            return True # Indicate success

        except Exception as e:
            print(f"An error occurred during vector store update: {e}")
            # Clean up potentially partially created store?
            # if os.path.exists(kb_path):
            #     shutil.rmtree(kb_path) # Optional: remove partial store on failure
            return False # Indicate failure

    @staticmethod
    def load_vectorstore(kb_path=constants.VECTORSTORE_PATH):
        """Loads the FAISS vector store from the specified path."""
        if not os.path.exists(kb_path) or not os.listdir(kb_path): # Check if dir exists and is not empty
            print(f"Vector store path '{kb_path}' not found or is empty. Cannot load.")

            return None

        print(f"Loading vector store from: {kb_path}")
        try:
            embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
            vectorstore = FAISS.load_local(
                kb_path, embeddings, allow_dangerous_deserialization=True
            )
            print("Vector store loaded successfully.")
            return vectorstore
        except Exception as e:
            print(f"Error loading vector store from '{kb_path}': {e}")

            return None
