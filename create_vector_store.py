import os
import json
import shutil
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DOCS_PATH="./recipes/"
VECTORSTORE_PATH = "./vectordb"

if os.path.exists(VECTORSTORE_PATH):
    shutil.rmtree(VECTORSTORE_PATH)
    print("Vector store directory removed.")

def format_recipe(recipe):
    name = recipe.get("name", "")
    desc = recipe.get("description", "")
    steps = "\n".join(step["instruction"] for step in recipe.get("steps", []))
    ingredients_str = ""

    for step in recipe.get("steps", []):
      ing = step.get("ingredients")
      for ing in ing:
        ingredients_str += ing.get("food", {}).get("name", "") + " : " + str(ing.get("amount", "")) + " "
        if ing.get("unit", {}):
          ingredients_str += ing.get("unit", {}).get("name", "") + "\n"
        else:
          ingredients_str += "\n"
    
    return f"Recipe: {name}\n\nDescription:\n{desc}\n\nIngredients:\n{ingredients_str}\n\nSteps:\n{steps}"

documents = []
recpies = os.listdir(DOCS_PATH)
recipes = [f for f in recpies if f.endswith('.json')]
for recipe in recipes:
  RECIPE_PATH = DOCS_PATH + recipe 
  with open(RECIPE_PATH, 'r') as f:
      data = json.load(f)

  doc_text = format_recipe(data)
  documents.append(Document(page_content=doc_text, metadata={"source": "recipe.json"}))


embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
vectorstore = FAISS.from_documents(documents, embeddings)
vectorstore.save_local(VECTORSTORE_PATH)
print("Vector store created.")