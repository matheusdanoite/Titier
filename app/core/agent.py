from llama_index.core import VectorStoreIndex, StorageContext, Document
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.tools.google import GoogleSearchToolSpec
from app.db.vector_store import VectorDB
import os

class StudyAgent:
    """
    Agente de Estudo Orquestrado pelo LlamaIndex.
    Integra RAG local com Google Search.
    """
    def __init__(self, vector_db: VectorDB, google_api_key: str = None, google_cse_id: str = None):
        self.vector_db = vector_db
        self.google_api_key = google_api_key
        self.google_cse_id = google_cse_id
        self.index = None
        self.agent = None

    def build_index(self, processed_content):
        """
        Cria o índice LlamaIndex a partir do conteúdo processado.
        """
        documents = []
        for item in processed_content:
            text = f"[Página {item['page']}] {item['content']}"
            metadata = {"page": item["page"], "type": item["type"]}
            documents.append(Document(text=text, metadata=metadata))

        # Configurar Qdrant como Vector Store no LlamaIndex
        vector_store = QdrantVectorStore(
            client=self.vector_db.client,
            collection_name=self.vector_db.collection_name
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        self.index = VectorStoreIndex.from_documents(
            documents, 
            storage_context=storage_context
        )

    def setup_agent(self, llm):
        """
        Configura o agente com ferramentas.
        """
        tools = []
        if self.google_api_key and self.google_cse_id:
            google_spec = GoogleSearchToolSpec(
                key=self.google_api_key, 
                cx=self.google_cse_id
            )
            tools.extend(google_spec.to_tool_list())

        # Adicionar ferramenta de busca no próprio índice (RAG)
        query_engine_tool = self.index.as_query_engine().as_tool(
            name="pdf_search",
            description="Busca informações técnicas dentro do arquivo PDF carregado."
        )
        tools.append(query_engine_tool)

        self.agent = FunctionCallingAgentWorker.from_tools(
            tools,
            llm=llm,
            verbose=True
        ).as_agent()

    def ask(self, query: str):
        if not self.agent:
            raise RuntimeError("Agente não configurado.")
        return self.agent.chat(query)
