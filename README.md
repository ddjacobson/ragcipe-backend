# :sushi: RAGcipe 
#### An intuitive way to chat with your recipes!
Meet Ragcipe, your new cuiliary companion!
Ragcipe is able to query a ground-truth knowledge base of .json files downloaded from Tandoor. 
We are working on further integration with the Tandoor API.

## ⚙️ Components

### 📚 Knowledge Base Manager
  The kb-manager updates the FAISS on-disk vector store based on the state of the file knowledge base.
  

### 🧠 RAG Engine
  The RAG Engine has the following duties
  - Initialize the LLM
  - Query the knowledge base
  - Reload (update) the LLM's vector store by interacting with the Knowledge Base Manager
  - Build the RAG chain based on the currently loaded vector store.
