import os
from dotenv import load_dotenv
from app.core.inference import InferenceEngine
from app.core.pdf_processor import PDFProcessor
from app.db.vector_store import VectorDB
from app.core.agent import StudyAgent

# Carregar chaves de API do Google (.env)
load_dotenv()

def bootstrap_app(model_path: str, pdf_path: str):
    print("--- [1] Inicializando Engines ---")
    # Configuração para Windows (CUDA) ou Mac (Metal) é automática no llama-cpp-python
    engine = InferenceEngine(model_path=model_path)
    # No caso multimodal, carregar o chat handler se necessário
    engine.load_model(is_multimodal=True) 

    print("--- [2] Processando PDF (Híbrido) ---")
    processor = PDFProcessor(inference_engine=engine)
    content = processor.process_pdf(pdf_path)

    print("--- [3] Configurando Banco Vetorial ---")
    db = VectorDB()
    db.create_collection()

    print("--- [4] Orquestrando Agente Estudante ---")
    agent = StudyAgent(
        vector_db=db,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        google_cse_id=os.getenv("GOOGLE_CSE_ID")
    )
    agent.build_index(content)
    
    # Usar o LlamaIndex wrapper para o LLM local no agente
    # Nota: No código real, integraríamos o LlamaCPP (LlamaIndex) aqui
    from llama_index.llms.llama_cpp import LlamaCPP
    llm = LlamaCPP(model_path=model_path, temperature=0.1)
    
    agent.setup_agent(llm=llm)

    return agent

if __name__ == "__main__":
    from app.utils.downloader import check_and_download_all, MODELS
    
    # Exemplo de uso
    MODELS_DIR = "./models"
    PDF_PATH = "./data/pdfs/meu_estudo.pdf" # Caminho do PDF de teste

    # [Novo] Garante que os modelos do Hugging Face estejam presentes
    print("--- [0] Verificando Modelos ---")
    downloaded_paths = check_and_download_all(MODELS_DIR)
    
    # Define o caminho do modelo principal (MiniCPM para o bootstrap)
    MODEL_PATH = downloaded_paths.get("minicpm")

    if MODEL_PATH and os.path.exists(MODEL_PATH) and os.path.exists(PDF_PATH):
        app_agent = bootstrap_app(MODEL_PATH, PDF_PATH)
        
        print("\n--- [Pronto] Agente Ativo ---")
        prompt = "Explique o gráfico da página 1 e pesquise no Google sobre as tendências atuais desse tema."
        response = app_agent.ask(prompt)
        print(f"\nAgente: {response}")
    else:
        if not os.path.exists(PDF_PATH):
            print(f"Aviso: PDF não encontrado em {PDF_PATH}. Coloque um arquivo para testar.")
        else:
            print("Erro ao carregar os modelos necessários.")
