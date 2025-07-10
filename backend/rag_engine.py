import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.messages import AIMessage, HumanMessage
import constants as constants
import kb_manager # Import the refactored knowledge base manager

class RAGEngine:
    def __init__(self):
        print("Initializing RAGEngine...")
        self.llm = self._initialize_llm()
        self.vectorstore = None
        self.rag_chain = None
        self.reload_vectorstore() # Load initial vector store and build chain

    def _initialize_llm(self):
        """Initializes the Language Model."""
        print(f"Initializing LLM: {constants.LLM_MODEL_NAME}")
        try:
            llm = ChatGoogleGenerativeAI(
                model=constants.LLM_MODEL_NAME,
                google_api_key=constants.LLM_API_KEY,
                temperature=constants.LLM_TEMPERATURE
            )
            print("LLM initialized successfully.")
            return llm
        except Exception as e:
            print(f"Error initializing LLM: {e}")
            raise # Re-raise exception to prevent engine from starting in a bad state

    def _build_rag_chain(self):
        """Builds the RAG chain using the current vector store. This method should be called after a vector store update"""
        if not self.vectorstore:
            print("Error: Cannot build RAG chain without a loaded vector store.")
            return None

        print("Building RAG chain...")
        try:
            retriever = self.vectorstore.as_retriever(search_kwargs={'k': 3})

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

            history_aware_retriever = create_history_aware_retriever(
                self.llm, retriever, contextualize_q_prompt
            )

            qa_system_prompt = """You are an assistant for answering questions about recipes.
            Use the following pieces of retrieved context to answer the question.

            # Constraint
            1. Think deeply and multiple times about the user's question. You must understand the intent of their question and provide the most appropriate answer. Ask yourself 'why' to understand the context.
            2. When you don't have retrieved context for the question or the retrieved documents are irrelevant, state that the available recipes do not contain that specific information, clearly restating what was asked for.
            3. Use five sentences maximum. Keep the answer concise but logical/natural/in-depth.
            4. If the query is general-information (e.g., "How many cups are in a quart?"), answer correctly without solely relying on recipe context.
            5. Base your answer *primarily* on the retrieved context if available and relevant. If a questions is not contextually relevent based on the history, disregard and attempt to clear up confusion. If context is available use it.
            6. Be conversational with the user.
            7. If giving a list, format nicely in a human readable list, ordered or unordered. If giving ingredients or steps, please give as much detail as possible.
            8. If asked for something relating to the knowledge-base, use only the retrived knowledge. Do not reference chat history. It is okay to relate recipe names with their filenames
            9. **Format your entire response using Markdown.** Use features like lists, bolding, etc., where appropriate for readability.
            Context:
            {context}"""

            qa_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", qa_system_prompt),
                    MessagesPlaceholder("chat_history"),
                    ("human", "{input}"),
                ]
            )

            question_answer_chain = create_stuff_documents_chain(self.llm, qa_prompt)

            rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
            print("RAG chain built successfully.")
            return rag_chain
        except Exception as e:
            print(f"Error building RAG chain: {e}")
            return None # Return None if chain building fails

    def reload_vectorstore(self):
        """Reloads the vector store from disk and rebuilds the RAG chain."""
        print("Attempting to reload vector store...")
        # Load vector store from disk - ensuring consistency
        self.vectorstore = kb_manager.KnowledgeBaseManager.load_vectorstore(constants.VECTORSTORE_PATH)
        if self.vectorstore:
            print("Vector store reloaded. Rebuilding RAG chain...")
            self.rag_chain = self._build_rag_chain()
        else:
            print("Failed to reload vector store. RAG chain might be outdated or non-functional.")
            self.rag_chain = None # Ensure chain is None if vectorstore failed to load

    def query(self, user_question: str, serializable_chat_history: list, selected_recipe_filename: str | None = None):
        """
        Processes a user question using the RAG chain.
        Updates the serializable chat history in place.
        """
        if not self.rag_chain:
            print("Error: RAG chain is not available. Cannot process query.")
            # Ensure history is not modified if we can't process
            return "Sorry, the recipe query engine is not available right now."

        # Convert serializable history back to Langchain messages
        langchain_chat_history = []
        for msg_data in serializable_chat_history:
            if msg_data.get('type') == 'human':
                langchain_chat_history.append(HumanMessage(content=msg_data['content']))
            elif msg_data.get('type') == 'ai':
                langchain_chat_history.append(AIMessage(content=msg_data['content']))

        # Modify the question if a recipe context is provided
        effective_question = user_question
        if selected_recipe_filename:
            effective_question = f"Regarding the recipe '{selected_recipe_filename}': {user_question}"
            print(f"Querying with context from selected recipe: {selected_recipe_filename}")

        try:
            print(f"Invoking RAG chain with question: '{effective_question[:50]}...'") # Log truncated question
            response = self.rag_chain.invoke({
                "input": effective_question,
                "chat_history": langchain_chat_history
            })
            answer = response["answer"]

            # Append the *original* user question and AI response to the serializable history
            serializable_chat_history.append({'type': 'human', 'content': user_question})
            serializable_chat_history.append({'type': 'ai', 'content': answer})

            # Limit history size (simple approach)
            max_history_items = 10
            if len(serializable_chat_history) > max_history_items * 2:
                serializable_chat_history[:] = serializable_chat_history[-(max_history_items * 2):]

            print("RAG chain invocation successful.")
            return answer
        except Exception as e:
            print(f"\nAn error occurred during RAG chain invocation: {e}")
            # Avoid modifying history on error
            return "Sorry, an error occurred while processing your question."

