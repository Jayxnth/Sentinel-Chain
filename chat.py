import os
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "chroma_db")

def start_chat():
    print("\n[*] Initializing NLP Chat Interface...")
    
    if not os.path.exists(DB_DIR):
        print("[!] ChromaDB directory not found. Please run ingest first.")
        return
        
    # Same local offline embeddings used in ingestion
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    
    # Retrieve top 10 chunks related to the user query locally
    retriever = vectorstore.as_retriever(search_kwargs={"k": 10}) 
    
    # Initialize the Gemini generative AI for understanding and compiling answers
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)
    
    print("\n" + "="*60)
    print("Welcome to Sentinel-Chain AI Core Chat")
    print("Type your questions about the logs in plain English.")
    print("Type 'exit' or 'quit' to close the interface.")
    print("="*60 + "\n")
    
    chat_history = []
    
    while True:
        try:
            user_input = input("Sentinel-Chain> ")
            if user_input.strip().lower() in ['exit', 'quit']:
                print("Exiting chat loop. Stay safe!")
                break
                
            if not user_input.strip():
                continue
                
            # Perform local embedding vector map and document retrieval
            docs = retriever.invoke(user_input)
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # Construct Generative Prompt with only top 10 relevant context bits
            history_str = ""
            for msg in chat_history[-6:]:  # Keep last 3 exchanges
                role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                history_str += f"{role}: {msg.content}\n"
                
            full_prompt = (
                "You are Sentinel-Chain AI Core, an expert cybersecurity assistant. "
                "Use the following pieces of retrieved log context to answer the user's question. "
                "If you don't know the answer or the context doesn't contain it, just say that you don't know based on the logs. "
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
            
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=answer))
            
        except KeyboardInterrupt:
            print("\nExiting chat loop. Stay safe!")
            break
        except Exception as e:
            print(f"[!] Error: {e}")

if __name__ == "__main__":
    start_chat()
