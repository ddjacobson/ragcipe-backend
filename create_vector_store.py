import os
import json
import shutil
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DOCS_PATH="./recipes/"
VECTORSTORE_PATH = "./vectordb"

def format_recipe(recipe):
    """Formats the recipe JSON data into a string for embedding."""
    name = recipe.get("name", "")
    desc = recipe.get("description", "")
    steps = "\n".join(step["instruction"] for step in recipe.get("steps", []))
    ingredients_str = ""

    for step in recipe.get("steps", []):
        # Corrected iteration over ingredients list
        ing = step.get("ingredients", []) # Ensure 'ingredients' exists and default to empty list
        for ingredient_item in ing: # Iterate through the list of ingredients
            ingredients_str += ingredient_item.get("food", {}).get("name", "") + " : " + str(ingredient_item.get("amount", "")) + " "
            if ingredient_item.get("unit", {}):
                ingredients_str += ingredient_item.get("unit", {}).get("name", "") + "\n"
            else:
                ingredients_str += "\n"
    
    return f"Recipe: {name}\n\nDescription:\n{desc}\n\nIngredients:\n{ingredients_str}\n\nSteps:\n{steps}"

# def update_vector_store():
    """Reads all JSON recipes from DOCS_PATH, creates embeddings, and saves a new vector store."""
    print("Starting vector store update...")
    if os.path.exists(VECTORSTORE_PATH):
        try:
            shutil.rmtree(VECTORSTORE_PATH)
            print(f"Existing vector store at '{VECTORSTORE_PATH}' removed.")
        except OSError as e:
            print(f"Error removing existing vector store: {e}")
            return False # Indicate failure

    documents = []
    try:
        if not os.path.exists(DOCS_PATH):
            os.makedirs(DOCS_PATH)
            print(f"Created recipes directory at '{DOCS_PATH}'")
            
        recipe_files = [f for f in os.listdir(DOCS_PATH) if f.endswith('.json')]
        print(f"Found {len(recipe_files)} recipe files in '{DOCS_PATH}'.")

        for recipe_file in recipe_files:
            recipe_path = os.path.join(DOCS_PATH, recipe_file)
            try:
                with open(recipe_path, 'r') as f:
                    data = json.load(f)
                doc_text = format_recipe(data)
                # Use the filename as part of the source metadata
                documents.append(Document(page_content=doc_text, metadata={"source": recipe_file})) 
            except json.JSONDecodeError:
                print(f"Warning: Skipping invalid JSON file: {recipe_file}")
            except Exception as e:
                 print(f"Warning: Error processing file {recipe_file}: {e}")


        if not documents:
            print("No valid documents found to create vector store.")
            # Create an empty placeholder if needed, or handle appropriately
            # For now, just log and exit the function cleanly
            return True # Indicate success (no documents, nothing to index)

        print(f"Processing {len(documents)} documents for vector store.")
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        vectorstore = FAISS.from_documents(documents, embeddings)
        vectorstore.save_local(VECTORSTORE_PATH)
        print(f"Vector store successfully created/updated at '{VECTORSTORE_PATH}'.")
        return True # Indicate success

    except Exception as e:
        print(f"An error occurred during vector store update: {e}")
        return False # Indicate failure


# Keep the main execution block if you want to run this script directly
# if __name__ == '__main__':
    # update_vector_store()

# Removed old script logic outside the function