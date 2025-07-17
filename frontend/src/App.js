import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { speak } from './utils/tts'; // Import the speak function
import './App.css';

// Define the base URL for the API. Use environment variables in a real app.
const API_BASE_URL = 'http://localhost:5000';

// --- SVG Icons ---

const TrashIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="trash-icon">
    <polyline points="3 6 5 6 21 6"></polyline>
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
    <line x1="10" y1="11" x2="10" y2="17"></line>
    <line x1="14" y1="11" x2="14" y2="17"></line>
  </svg>
);

const MicrophoneIcon = ({ isListening }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill={isListening ? "red" : "currentColor"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mic-icon">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
    <line x1="12" y1="19" x2="12" y2="23"></line>
    <line x1="8" y1="23" x2="16" y2="23"></line>
  </svg>
);

// Speaker Icon for TTS Toggle
const SpeakerIcon = ({ isMuted }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`speaker-icon ${isMuted ? 'muted' : ''}`}>
    {isMuted ? (
      <>
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
        <line x1="23" y1="9" x2="17" y2="15"></line>
        <line x1="17" y1="9" x2="23" y2="15"></line>
      </>
    ) : (
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
    )}
  </svg>
);


function App() {
  // --- State Management ---
  const [recipes, setRecipes] = useState([]);
  const [chatHistory, setChatHistory] = useState([]);
  const [userInput, setUserInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedRecipe, setSelectedRecipe] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [removeStatus, setRemoveStatus] = useState('');
  const [isRemoving, setIsRemoving] = useState(false);
  const [isRemovingRecipe, setIsRemovingRecipe] = useState(null);
  const [isListening, setIsListening] = useState(false);
  const [speechError, setSpeechError] = useState('');
  const [speechSupported, setSpeechSupported] = useState(true);
  const [isTtsEnabled, setIsTtsEnabled] = useState(true); // State for TTS toggle
  const [isSpeechMode, setIsSpeechMode] = useState(false); // State for speech mode
  const [isSpeaking, setIsSpeaking] = useState(false); // State for TTS activity

  // --- Refs ---
  const chatBoxRef = useRef(null);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);

  // --- Effects ---

  // Initialize Speech Recognition
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("Speech Recognition API not supported.");
      setSpeechError("Speech recognition not supported.");
      setSpeechSupported(false);
      return;
    }
    setSpeechSupported(true);

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
      let transcript = '';
      for (let i = 0; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          transcript += event.results[i][0].transcript;
        }
      }
      
      if (transcript) {
        handleSendMessage(transcript.trim());
        setUserInput('');
      }
    };

    recognition.onerror = (event) => {
      let msg = `Speech error: ${event.error}`;
      if (event.error === 'no-speech') msg = "No speech detected.";
      if (event.error === 'audio-capture') msg = "Microphone error.";
      if (event.error === 'not-allowed') msg = "Microphone permission denied.";
      setSpeechError(msg);
      setIsListening(false);
    };

    recognition.onend = () => {
      if (isSpeechMode && !isSpeaking) {
        setIsListening(true);
        recognition.start();
      }
      
    };

    recognition.onspeechend = () => {
      recognition.stop();
    };

    if (!isSpeaking) {
     recognition.start(); // start listnening if not speaking
    }

    recognitionRef.current = recognition;
  }, [isSpeechMode, isListening, isSpeaking]);

  // Fetch initial data on mount
  const fetchInitialData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/init`, { credentials: 'include' });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      setRecipes(data.recipes || []);
      setChatHistory(data.chat_history || []);
      setSelectedRecipe(data.selected_recipe || null);
      if (!data.chat_history || data.chat_history.length === 0) {
        setChatHistory([{ type: 'ai', content: 'Welcome! Ask me anything about the recipes.' }]);
      }
    } catch (error) {
      console.error("Error fetching initial data:", error);
      setChatHistory([{ type: 'ai', content: `Error loading data: ${error.message}` }]);
      setRecipes([]);
      setSelectedRecipe(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  // Auto-scroll chat and handle TTS on new messages
  useEffect(() => {
    if (chatBoxRef.current) {
      chatBoxRef.current.scrollTop = chatBoxRef.current.scrollHeight;
    }
    // Speak the last message if it's from the AI and TTS is enabled
    if (chatHistory.length > 0) {
      const lastMessage = chatHistory[chatHistory.length - 1];
      if (lastMessage.type === 'ai' && !lastMessage.isLoading && isTtsEnabled) {
        speak(
          lastMessage.content,
          () => setIsSpeaking(true),  // onStart callback
          () => setIsSpeaking(false) // onEnd callback
        );
      }
    }
  }, [chatHistory, isTtsEnabled]);

  // --- Event Handlers ---

  const handleInputChange = (event) => {
    setUserInput(event.target.value);
  };

  // Handle clicking a recipe name
  const handleRecipeSelect = async (recipeFilename) => {
    if (isLoading) return; // Prevent selection changes during API calls
    setIsLoading(true);
    try {
      // Optional: Notify backend about the selection change if needed for session persistence
      // (Current backend doesn't strictly require this, but good practice for state sync)
      const response = await fetch(`${API_BASE_URL}/api/select_recipe`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ recipe: recipeFilename }),
        credentials: 'include', // Send session cookie
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      // Update state locally
      setSelectedRecipe(recipeFilename);
      // No chat message needed, UI indicator is sufficient
    } catch (error) {
      console.error("Error selecting recipe:", error);
      // Add error message to chat
      setChatHistory(prev => [...prev, { type: 'ai', content: `Error setting recipe context: ${error.message}` }]);
    } finally {
        setIsLoading(false);
    }

  };

  // Handle clearing the recipe selection
  const handleClearRecipeSelection = async () => {
    if (isLoading || !selectedRecipe) return;
    setIsLoading(true);
     try {
        // Optional: Notify backend about the selection clear
        const response = await fetch(`${API_BASE_URL}/api/select_recipe`, { // Use the same endpoint with null
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ recipe: null }),
            credentials: 'include',
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        setSelectedRecipe(null);
        // No chat message needed, UI indicator is sufficient
    } catch (error) {
        console.error("Error clearing recipe selection:", error);
        setChatHistory(prev => [...prev, { type: 'ai', content: `Error clearing recipe context: ${error.message}` }]);
    } finally {
        setIsLoading(false);
    }
  };

  const handleSendMessage = async (questionText = null) => {
    // Use provided text or fallback to userInput state, then trim
    const question = (questionText !== null ? questionText : userInput).trim();
    if (!question || isLoading) return;

    setIsLoading(true);
    // Add user message immediately to history
    const newUserMessage = { type: 'human', content: question };
    setChatHistory(prev => [...prev, newUserMessage]);
    setUserInput(''); // Clear input regardless of source

    // Add a temporary thinking message for the bot
    const thinkingMessage = { type: 'ai', content: '...', isLoading: true };
    setChatHistory(prev => [...prev, thinkingMessage]);

    try {
      const response = await fetch(`${API_BASE_URL}/api/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        // Send the question AND the selected recipe
        body: JSON.stringify({ 
            question: question, 
            selected_recipe: selectedRecipe // Include the selected recipe context
         }),
        credentials: 'include', // Important for sending session cookie
      });

      if (!response.ok) {
         // Try to parse error from backend
         let errorMsg = `HTTP error! status: ${response.status}`;
         try {
             const errorData = await response.json();
             errorMsg = errorData.error || errorMsg;
         } catch (parseError) {
             // Ignore if response isn't JSON
         }
         throw new Error(errorMsg);
       }

      const data = await response.json();

      // Update chat history with the response from the backend
      // (Assuming backend returns the full, updated history)
      setChatHistory(data.chat_history || []); 

    } catch (error) {
      console.error("Error sending message:", error);
       // Replace thinking message with error message
       setChatHistory(prev => {
          // Find the index of the thinking message (usually the last one)
          const thinkingIndex = prev.findIndex(msg => msg.isLoading);
          if (thinkingIndex !== -1) {
            // Replace the loading indicator with the error
            const updatedHistory = [...prev];
            updatedHistory[thinkingIndex] = { type: 'ai', content: `Sorry, an error occurred: ${error.message}` };
            return updatedHistory;
          }
          // If no loading indicator (shouldn't happen), just add error
          return [...prev, { type: 'ai', content: `Sorry, an error occurred: ${error.message}` }];
        });
    } finally {
      setIsLoading(false);
    }
  };

  // Handle Enter key press in textarea
  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault(); // Prevent newline
      handleSendMessage(); // Call without args to use current userInput
    }
  };

  const handleClearHistory = async () => {
    if (isLoading) return;
    setIsLoading(true);
    try {
        const response = await fetch(`${API_BASE_URL}/api/clear`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include', // Send session cookie
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        // Clear history locally and add confirmation
        setChatHistory([{ type: 'ai', content: 'Chat history cleared. Ask me something new!' }]);
        setSelectedRecipe(null); // Also clear recipe selection when clearing history
    } catch (error) {
        console.error("Error clearing history:", error);
        // Add error message to chat
        setChatHistory(prev => [...prev, { type: 'ai', content: `Error clearing history: ${error.message}` }]);
    } finally {
        setIsLoading(false);
    }
};

// --- File Upload Handlers ---
const handleFileChange = (event) => {
  if (event.target.files && event.target.files[0]) {
      const file = event.target.files[0];
      // Basic check for JSON extension client-side (backend validates again)
      if (file.type === 'application/json' || file.name.endsWith('.json')) {
          setSelectedFile(file);
          setUploadStatus(''); // Clear previous status
      } else {
          setSelectedFile(null);
          setUploadStatus('Please select a .json file.');
          // Clear the input visually
          if (fileInputRef.current) {
             fileInputRef.current.value = null;
          }
      }
  } else {
      setSelectedFile(null); // Handle case where selection is cancelled
      setUploadStatus('');
  }
};

const handleDataSourceSync = async () => {
  console.log("Syncing data source...");

  // need to get credentials... hardcode them now


  const response = await fetch(`${API_BASE_URL}/data/reload-source`, {
    method: 'POST',
    body: {},
    credentials: 'include', // Important for session cookie 
    // Note: Don't set 'Content-Type': 'multipart/form-data' manually,
    // fetch does it automatically when using FormData and sets the boundary.
  });


};

const handleFileUpload = async () => {
  if (!selectedFile || isUploading) return;

  setUploadStatus('Uploading...');
  setIsUploading(true); // Disable button

  const formData = new FormData();
  formData.append('recipeFile', selectedFile); // Match the key expected by Flask

  try {
    const response = await fetch(`${API_BASE_URL}/api/upload_recipe`, {
      method: 'POST',
      body: formData,
      credentials: 'include', // Important for session cookie 
      // Note: Don't set 'Content-Type': 'multipart/form-data' manually,
      // fetch does it automatically when using FormData and sets the boundary.
    });

    const data = await response.json(); // Always try to parse JSON first

    if (!response.ok) {
        // Use error message from backend if available, otherwise use status text
        throw new Error(data.error || `HTTP error! status: ${response.status}`);
    }
    
    // Use a more specific success message from backend if available
    setUploadStatus(data.message || 'Upload successful!'); 
    setRecipes(data.recipes || []); // Update the recipe list
    setSelectedFile(null); // Clear the selection state
    // Clear the file input visually
    if (fileInputRef.current) {
        fileInputRef.current.value = null;
    }


  } catch (error) {
    console.error("Error uploading file:", error);
    // Display a user-friendly error message
    setUploadStatus(`Error: ${error.message || 'Upload failed. Check console for details.'}`);
  } finally {
    setIsUploading(false); // Re-enable button
  }
};

// --- Vector Store Removal Handler ---
const handleRemoveVectorStore = async () => {
  if (isRemoving) return;

  // Optional: Add a confirmation dialog
  if (!window.confirm('Are you sure you want to remove the vector store? This action cannot be undone.')) {
      return;
  }

  setRemoveStatus('Removing vector store...');
  setIsRemoving(true);

  try {
    const response = await fetch(`${API_BASE_URL}/api/remove_vector_store`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json', // Although no body, setting header is good practice
      },
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || `HTTP error! status: ${response.status}`);
    }

    setRemoveStatus(data.message || 'Vector store removed.');
    // Clear any existing upload status as well
    setUploadStatus('');

  } catch (error) {
    console.error("Error removing vector store:", error);
    setRemoveStatus(`Error: ${error.message || 'Failed to remove vector store.'}`);
  } finally {
    setIsRemoving(false);
  }
};

// --- Single Recipe Removal Handler ---
const handleRemoveRecipe = async (recipeFilename, event) => {
    event.stopPropagation(); // Prevent triggering handleRecipeSelect when clicking the icon

    if (isRemovingRecipe) return; // Prevent multiple simultaneous removals

    if (!window.confirm(`Are you sure you want to remove the recipe "${recipeFilename}"? This action cannot be undone.`)) {
        return;
    }

    setIsRemovingRecipe(recipeFilename); // Indicate which recipe is being removed
    setRemoveStatus(`Removing "${recipeFilename}"...`); // Update status
    setUploadStatus(''); // Clear upload status

    try {
        const response = await fetch(`${API_BASE_URL}/api/remove_recipe`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ filename: recipeFilename }),
            credentials: 'include',
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        setRemoveStatus(data.message || 'Recipe removed.');
        setRecipes(data.recipes || []); // Update the recipe list

        // If the removed recipe was selected, clear the selection state
        if (selectedRecipe === recipeFilename) {
            setSelectedRecipe(null);
        }
         // clear chat history
        // Alternatively, if the backend indicates selection was cleared:
        // if (data.cleared_selection) {
        //     setSelectedRecipe(null);
        // }

    } catch (error) {
        console.error(`Error removing recipe ${recipeFilename}:`, error);
        setRemoveStatus(`Error removing "${recipeFilename}": ${error.message}`);
    } finally {
        setIsRemovingRecipe(null); // Finish removal process
    }
};

  const handleMicClick = () => {
    if (isSpeaking) return; // Prevent listening while speaking
    if (!recognitionRef.current) {
        setSpeechError("Speech recognition not initialized.");
        return;
    }
    if (isListening) {
        console.log("Stopping speech recognition...");
        recognitionRef.current.stop();
        setIsListening(false);
    } else {
        try {
            setSpeechError('');
            if (isSpeechMode) {
              recognitionRef.current.continuous = true;
              recognitionRef.current.interimResults = true;
            } else {
              recognitionRef.current.continuous = false;
              recognitionRef.current.interimResults = false;
            }
            recognitionRef.current.start();
            setIsListening(true);
        } catch (err) {
            console.error("Error starting speech recognition:", err);
            setSpeechError("Could not start listening. Please check microphone permissions.");
            setIsListening(false);
        }
    }
  };

  // --- Render ---
  return (
    <div className="container">
      <aside className="sidebar">
        <h1 className="logo">RAGcipe</h1>
        <h2>Available Recipes</h2>
        <ul id="recipe-list">
          {recipes.length > 0 ? (
            recipes.map((recipe, index) => (
              <li
                key={index}
                className={`recipe-item ${selectedRecipe === recipe ? 'selected' : ''} ${isRemovingRecipe === recipe ? 'removing' : ''}`}
                onClick={() => handleRecipeSelect(recipe)}
                aria-current={selectedRecipe === recipe ? 'true' : 'false'} // Accessibility
              >
                <span className="recipe-name">{recipe}</span> 
                {/* Add remove button/icon */}
                <button
                  className="remove-recipe-btn"
                  onClick={(e) => handleRemoveRecipe(recipe, e)}
                  disabled={!!isRemovingRecipe} // Disable all remove buttons during removal
                  title={`Remove ${recipe}`}
                  aria-label={`Remove recipe ${recipe}`}
                >
                  {isRemovingRecipe === recipe ? '...' : <TrashIcon />}
                </button>
              </li>
            ))
          ) : (
            <li>{isLoading && !recipes.length ? 'Loading recipes...' : 'No recipes found.'}</li> 
          )}
        </ul>

         {/* --- Upload & Manage Section --- */}
         <div className="manage-section">
          <h3>Manage Recipes & Index</h3>
          <div className="file-input-wrapper">
            <button type="button" onClick={() => fileInputRef.current?.click()} disabled={isUploading || isRemoving} className="btn-like">
              Choose File (.json)
            </button>
            <input
                ref={fileInputRef} // Assign ref
                type="file"
                accept=".json,application/json" // More specific accept types
                onChange={handleFileChange}
                disabled={isUploading || isRemoving}
                style={{ display: 'none' }} // Hide the default input
                aria-label="Select JSON recipe file to upload"
            />
             {selectedFile && <span className="selected-file-name">{selectedFile.name}</span>}
          </div>
          <div className="button-group">
            <button
                onClick={handleFileUpload}
                disabled={!selectedFile || isUploading || isRemoving}
                className="action-button"
            >
                {isUploading ? 'Uploading...' : 'Upload Recipe'}
            </button>
            <button
                onClick={handleDataSourceSync}
                className="action-button"
            >
                {isUploading ? 'Syncing...' : 'Sync Recipes'}
            </button>
            <button
                onClick={handleRemoveVectorStore}
                disabled={isUploading || isRemoving}
                className="action-button danger-button" // Add danger class for styling
                title="Remove the indexed vector store (recipes files remain)"
            >
                 {isRemoving ? 'Removing...' : 'Remove Index'}
            </button>
          </div>
          {/* Display upload status messages */}
          {uploadStatus && (
             <p
               className={`status-message ${uploadStatus.startsWith('Error:') ? 'error' : (uploadStatus.startsWith('Success:') || uploadStatus.includes('uploaded')) ? 'success' : ''}`}
               aria-live="polite"
             >
                {uploadStatus}
             </p>
           )}
           {/* Display remove status messages */}
           {removeStatus && (
             <p
               className={`status-message ${removeStatus.startsWith('Error:') ? 'error' : 'success'}`}
               aria-live="polite"
             >
                {removeStatus}
             </p>
           )}
        </div>
         {/* --- End Manage Section --- */}

      </aside>

      <main className="chat-area">
        <div className="chat-header">
          <h2>Chat Your Recipes</h2>
          <button 
            id="clear-history-btn" 
            onClick={handleClearHistory} 
            disabled={isLoading}
            title="Clear chat messages and reset recipe context"
          >
            Clear History
          </button>
        </div>
        {/* Display selected recipe context */} 
        {selectedRecipe && (
           <div className="context-indicator">
             <span>Focusing on: <strong>{selectedRecipe}</strong></span>
             <button 
                onClick={handleClearRecipeSelection} 
                disabled={isLoading}
                className="clear-context-btn"
                title="Stop focusing on this recipe"
             >
                Clear Focus
             </button>
           </div>
         )}
        <div id="chat-box" ref={chatBoxRef}>
          {chatHistory.map((msg, index) => (
            <div 
              key={index} 
              className={`message ${msg.type === 'human' ? 'user-message' : 'bot-message'} ${msg.isLoading ? 'loading' : ''}`}
            >
              {/* Conditionally render Markdown for bot messages */}
              {msg.type === 'ai' ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                msg.content // Keep user messages as plain text
              )}
            </div>
          ))}
        </div>
        <div className="input-area">
          {speechError && <p className="error-message speech-error">{speechError}</p>}
          <textarea
            value={userInput}
            onChange={handleInputChange}
            onKeyPress={handleKeyPress}
            placeholder="Type your message or click the mic..."
            rows="3"
            disabled={isLoading}
          />
          <button onClick={handleMicClick} 
            disabled={isLoading || !speechSupported}
            className="mic-button" 
            title={isListening ? "Stop listening" : "Start listening"}>
            <MicrophoneIcon isListening={isListening} />
          </button>
          <button onClick={() => setIsSpeechMode(prev => !prev)} 
            disabled={isLoading || !speechSupported}
            className={`speech-mode-button ${isSpeechMode ? 'active' : ''}`}
            title={isSpeechMode ? "Deactivate speech mode" : "Activate speech mode"}>
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="M8 12h8"/><path d="M12 8v8"/></svg>
          </button>
          <button onClick={handleSendMessage} disabled={isLoading || !userInput.trim()} className="send-button">
            Send
          </button>
          <button 
            onClick={() => setIsTtsEnabled(prev => !prev)} 
            className="tts-button" 
            title={isTtsEnabled ? "Disable Text-to-Speech" : "Enable Text-to-Speech"}
          >
            <SpeakerIcon isMuted={!isTtsEnabled} />
          </button>
        </div>
      </main>
    </div>
  );
}

export default App;
