import os
from langchain.prompts.chat import ChatPromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_history_aware_retriever
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
import glob # Added for listing files
import constants


# --- Load API Key from environment variable ---
if not constants.LLM_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

# --- 1. Load vectorstore ---
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
vectorstore = FAISS.load_local(
    constants.VECTORSTORE_PATH, embeddings, allow_dangerous_deserialization=True
)

print(f"Initializing LLM: {constants.LLM_MODEL_NAME} via DeepSeek")

llm = ChatGoogleGenerativeAI(
    model=constants.LLM_MODEL_NAME,
    google_api_key=constants.LLM_API_KEY,  # Pass the key here
    temperature=1.0  # Set the temperature for randomness
    # You can add other parameters like temperature=0.7, etc.
)
print("LLM initialized.")

contextualize_q_system_prompt = """Given a chat history and the latest user question \
which might reference context in the chat history, formulate a standalone question \
which can be understood without the chat history. Do NOT answer the question, \
just reformulate it if needed and otherwise return it as is."""

contextualize_q_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)

prompt_template = """You are an assistant for answering questions about recipes.
Use the following pieces of retrieved context to answer the question.

# Constraint
1. Think deeply and multiple times about the user's question. You must understand the intent of their question and provide the most appropriate answer. Ask yourself 'why' to understand the context.
2. When you don't have retrieved context for the question or the retrieved documents are irrelevant, state that the available recipes do not contain that specific information, clearly restating what was asked for.
3. Use five sentences maximum. Keep the answer concise but logical/natural/in-depth.
4. If the query is general-information (e.g., "How many cups are in a quart?"), answer correctly without solely relying on recipe context.
5. Base your answer *primarily* on the retrieved context if available and relevant. If context is available use it.
6. Be conversational with the user.
7. If giving a list, format nicely in a human readable list, ordered or unordered. If giving ingredients or steps, please give as much detail as possible.
8. **Format your entire response using Markdown.** Use features like lists, bolding, etc., where appropriate for readability.

Context:
{context}"""

# Note: We put {context} in the system prompt. The {input} comes from the human message.
qa_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompt_template),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"), # The user's possibly-reformulated question
    ]
)

retriever = vectorstore.as_retriever(search_kwargs={'k': 3}) # Retrieve top 5 relevant chunks

history_aware_retriever = create_history_aware_retriever(
    llm, retriever, contextualize_q_prompt
)
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

rag_chain = create_retrieval_chain(
    history_aware_retriever, question_answer_chain, 
)

# --- Function to get RAG response ---
def get_rag_response(user_question: str, serializable_chat_history: list, selected_recipe_filename: str | None = None):
    """
    Invokes the RAG chain with the given question and chat history.
    Accepts and updates history in a serializable format (list of dictionaries).
    Optionally uses the context of a selected recipe filename.
    """
    # Convert serializable history back to Langchain messages
    langchain_chat_history = []
    for msg_data in serializable_chat_history:
        if msg_data.get('type') == 'human':
            langchain_chat_history.append(HumanMessage(content=msg_data['content']))
        elif msg_data.get('type') == 'ai':
            langchain_chat_history.append(AIMessage(content=msg_data['content']))
        # Add handling for other message types if necessary

    # Modify the question if a recipe context is provided
    effective_question = user_question
    if selected_recipe_filename:
        # Let's try a clear prefix. Adjust phrasing if needed based on results.
        effective_question = f"Regarding the recipe '{selected_recipe_filename}': {user_question}"
        print(f"Using context from selected recipe: {selected_recipe_filename}") # Optional: for debugging

    try:
        response = rag_chain.invoke({
            "input": effective_question, # Use the potentially modified question
            "chat_history": langchain_chat_history # Use the converted history
        })

        # Append the *original* user question and AI response to the serializable history
        serializable_chat_history.append({'type': 'human', 'content': user_question})
        serializable_chat_history.append({'type': 'ai', 'content': response["answer"]})
        
        # Limit history size (optional, adjust as needed)
        max_history_items = 10 
        if len(serializable_chat_history) > max_history_items * 2:
            # Keep the last 'max_history_items' pairs
            # Use slicing assignment to modify the list in place
            serializable_chat_history[:] = serializable_chat_history[-(max_history_items * 2):] 

        return response["answer"]
    except Exception as e:
        print(f"\nAn error occurred during RAG chain invocation: {e}")
        # Consider logging the error instead of just printing
        # Ensure the history list isn't partially modified on error if possible,
        # although in this structure it might be ok.
        return "Sorry, an error occurred while processing your question."

# --- Function to list recipe files ---
def list_recipes():
    """Lists the recipe files in the DOCS_PATH directory."""
    try:
        # Use glob to find markdown files, adjust pattern if needed
        recipe_files = glob.glob(os.path.join(constants.DOCS_PATH, "*.json")) 
        # Return only the base filename
        return [os.path.basename(f) for f in recipe_files]
    except Exception as e:
        print(f"Error listing recipes: {e}")
        return []

print("RAG chain created and ready.") # Changed print statement
