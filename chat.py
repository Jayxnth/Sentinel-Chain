import os
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "chroma_db")

def extract_filters(query):
    query_lower = query.lower()
    filters = {}
    
    # Check for VM restrictions
    if "vm1" in query_lower:
        filters["source_vm"] = "vm1"
    elif "vm2" in query_lower:
        filters["source_vm"] = "vm2"
        
    # Check for Log Type restrictions
    if "malware" in query_lower:
        filters["log_type"] = "malware"
    elif "intrusion" in query_lower:
        filters["log_type"] = "intrusion"
    elif "web" in query_lower:
        filters["log_type"] = "web"
    elif "http" in query_lower:
        filters["log_type"] = "http"
        
    return filters if filters else None

def start_chat():
    print("\n[*] Initializing NLP Chat Interface...")
    
    if not os.path.exists(DB_DIR):
        print("[!] ChromaDB directory not found. Please run ingest first.")
        return
        
    # Same local offline embeddings used in ingestion (force offline mode to bypass ConnectionReset)
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2", 
        model_kwargs={'local_files_only': True}
    )
    vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    
    # Initialize the Gemini generative AI
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)
    
    # Use native message array (bypassing deprecated ConversationBufferMemory)
    memory_history = []
    
    print("\n" + "="*60)
    print("Welcome to Sentinel-Chain AI Core Chat")
    print("Type your questions about the logs in plain English.")
    print("Type 'exit' or 'quit' to close the interface.")
    print("="*60 + "\n")
    
    while True:
        try:
            user_input = input("Sentinel-Chain> ")
            if user_input.strip().lower() in ['exit', 'quit']:
                print("Exiting chat loop. Stay safe!")
                break
                
            if not user_input.strip():
                continue
                
            # Filter the DB based on the query text (VMs / Log types)
            metadata_filters = extract_filters(user_input)
            
            if metadata_filters:
                search_kwargs = {"k": 10, "filter": metadata_filters}
                print(f"[*] Applying search filters: {metadata_filters}")
            else:
                search_kwargs = {"k": 10}
                
            retriever = vectorstore.as_retriever(search_kwargs=search_kwargs) 
            docs = retriever.invoke(user_input)
            
            if not docs:
                print("\nAI: I couldn't find any relevant logs for that query.\n")
                continue
            
            # Format context with citations (Issue 12)
            context_pieces = []
            for idx, doc in enumerate(docs):
                fn = doc.metadata.get('filename', 'unknown')
                lt = doc.metadata.get('log_type', 'unknown')
                ts = doc.metadata.get('timestamp', 'unknown')
                context_pieces.append(f"[Source {idx+1} | File: {fn} | Type: {lt} | Time: {ts}]\n{doc.page_content}")
            
            context = "\n\n".join(context_pieces)
            
            # Unpack memory into string 
            history_str = ""
            start_idx = max(0, len(memory_history) - 6)
            for i in range(start_idx, len(memory_history)):
                msg = memory_history[i]
                if isinstance(msg, HumanMessage):
                    history_str += f"User: {msg.content}\n"
                elif isinstance(msg, AIMessage):
                    history_str += f"Assistant: {msg.content}\n"
            
            # Construct Generative Prompt enforcing citations
            full_prompt = (
                "You are Sentinel-Chain AI Core, an expert cybersecurity assistant.\n"
                "Use the following pieces of retrieved log context to answer the user's question.\n"
                "If you don't know the answer or the context doesn't contain it, just say that you don't know based on the logs.\n"
                "CRITICAL: You MUST include source citations in your answer. For every finding, append the source reference used (e.g., [Source 1]).\n"
                "At the end of your answer, list the unique source files you referenced.\n"
                "Be concise, analytical, and reference specific log details when possible.\n\n"
                f"Context Logs:\n{context}\n\n"
            )
            
            if history_str:
                full_prompt += f"Recent Chat History:\n{history_str}\n\n"
                
            full_prompt += f"User Query: {user_input}"
            
            # Send exactly ONE API request directly to the Gemini LLM
            response = llm.invoke(full_prompt)
            answer = response.content
            print(f"\nAI: {answer}\n")
            
            # Save interactions to custom memory
            memory_history.append(HumanMessage(content=user_input))
            memory_history.append(AIMessage(content=answer))
            
        except KeyboardInterrupt:
            print("\nExiting chat loop. Stay safe!")
            break
        except Exception as e:
            print(f"[!] Error: {e}")

if __name__ == "__main__":
    start_chat()
