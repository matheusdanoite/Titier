"""
Cassio AI - Vector Store (Qdrant Embedded Mode)
Armazenamento vetorial local sem Docker
Suporta contexto por documento e busca global
"""
from pathlib import Path
from typing import Optional, List
import os
import hashlib

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue


class VectorStore:
    """
    Vector Store usando Qdrant em modo embedded.
    Persiste dados em disco local sem necessidade de servidor externo.
    Suporta contexto isolado por documento e busca global.
    """
    
    COLLECTION_NAME = "pdf_documents"
    DEFAULT_STORAGE = Path.home() / ".cassio" / "qdrant_data"
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        embedding_dim: int = 384  # paraphrase-multilingual-MiniLM-L12-v2
    ):
        self.storage_path = Path(storage_path) if storage_path else self.DEFAULT_STORAGE
        self.embedding_dim = embedding_dim
        self.client: Optional[QdrantClient] = None
        self.encoder = None
    
    def connect(self) -> "VectorStore":
        """Inicializa conexão com Qdrant local."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        print(f"[Qdrant] Conectando: {self.storage_path}")
        
        self.client = QdrantClient(path=str(self.storage_path))
        self._ensure_collection()
        
        print(f"[Qdrant] Conectado com sucesso!")
        return self
    
    def _ensure_collection(self):
        """Garante que a collection existe."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.COLLECTION_NAME for c in collections)
        
        if exists:
            # Verificar se a dimensão é compatível com o novo modelo (384)
            info = self.client.get_collection(self.COLLECTION_NAME)
            current_dim = info.config.params.vectors.size
            if current_dim != self.embedding_dim:
                print(f"[Qdrant] Dimensão incompatível ({current_dim} vs {self.embedding_dim}). Recriando collection...")
                self.client.delete_collection(self.COLLECTION_NAME)
                exists = False

        if not exists:
            print(f"[Qdrant] Criando collection: {self.COLLECTION_NAME} (Dim: {self.embedding_dim})")
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE
                )
            )
            # Criar índice para file_hash para buscas rápidas
            self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="file_hash",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="source",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
    
    def _get_encoder(self):
        """Lazy loading do encoder de embeddings com detecção de hardware."""
        if self.encoder is None:
            from sentence_transformers import SentenceTransformer
            import torch
            
            # Detecção automática de dispositivo
            device = "cpu"
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            
            model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            print(f"[Qdrant] Carregando encoder {model_name.split('/')[-1]} no dispositivo: {device.upper()}")
            
            self.encoder = SentenceTransformer(model_name, device=device)
        return self.encoder
    
    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """Calcula SHA256 hash do arquivo para identificação única."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def is_document_indexed(self, file_hash: str) -> bool:
        """Verifica se um documento já está indexado pelo hash."""
        if not self.client:
            self.connect()
        
        # Buscar por hash
        results = self.client.scroll(
            collection_name=self.COLLECTION_NAME,
            scroll_filter=Filter(
                must=[FieldCondition(key="file_hash", match=MatchValue(value=file_hash))]
            ),
            limit=1
        )
        
        return len(results[0]) > 0
    
    def get_indexed_documents(self) -> List[dict]:
        """Lista todos os documentos indexados com suas informações."""
        if not self.client:
            self.connect()
        
        # Buscar todos os pontos agrupando por source
        documents = {}
        offset = None
        
        while True:
            results, offset = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=["source", "file_hash"]
            )
            
            if not results:
                break
            
            for point in results:
                source = point.payload.get("source", "unknown")
                file_hash = point.payload.get("file_hash", "")
                
                if source not in documents:
                    documents[source] = {
                        "source": source,
                        "file_hash": file_hash,
                        "chunks_count": 0
                    }
                documents[source]["chunks_count"] += 1
            
            if offset is None:
                break
        
        return list(documents.values())
    
    def add_documents(
        self,
        texts: list[str],
        metadata: Optional[list[dict]] = None,
        batch_size: int = 32
    ) -> int:
        """
        Adiciona documentos ao vector store.
        Retorna número de documentos adicionados.
        """
        if not self.client:
            self.connect()
        
        encoder = self._get_encoder()
        
        # Gerar embeddings com normalização
        print(f"[Qdrant] Gerando embeddings para {len(texts)} documentos...")
        embeddings = encoder.encode(
            texts, 
            show_progress_bar=True,
            normalize_embeddings=True,
            batch_size=batch_size
        )
        
        # Obter próximo ID
        collection_info = self.client.get_collection(self.COLLECTION_NAME)
        start_id = collection_info.points_count
        
        # Criar points
        points = []
        for i, (text, embedding) in enumerate(zip(texts, embeddings)):
            payload = {"text": text}
            if metadata and i < len(metadata):
                payload.update(metadata[i])
            
            points.append(PointStruct(
                id=start_id + i,
                vector=embedding.tolist(),
                payload=payload
            ))
        
        # Upsert em batches
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=batch
            )
        
        print(f"[Qdrant] {len(points)} documentos adicionados!")
        return len(points)
    
    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.0,
        source_filter: Optional[str] = None,
        file_hash_filter: Optional[str] = None,
        highlight_only: bool = False,
        color_filter: Optional[str] = None
    ) -> list[dict]:
        """
        Busca semântica por documentos similares.
        
        Args:
            query: Texto da busca
            limit: Número máximo de resultados
            score_threshold: Score mínimo (0.0 a 1.0)
            source_filter: Filtrar por nome do arquivo (busca local)
            file_hash_filter: Filtrar por hash do arquivo (mais preciso)
            highlight_only: Se True, retorna apenas trechos grifados
            color_filter: Filtrar por cor específica (ex: 'verde', 'amarelo')
        
        Returns:
            Lista de payloads com scores
        """
        if not self.client:
            self.connect()
        
        encoder = self._get_encoder()
        query_vector = encoder.encode(
            query, 
            normalize_embeddings=True
        ).tolist()
        
        # Construir filtro
        conditions = []
        if file_hash_filter:
            conditions.append(FieldCondition(key="file_hash", match=MatchValue(value=file_hash_filter)))
        elif source_filter:
            conditions.append(FieldCondition(key="source", match=MatchValue(value=source_filter)))
            
        if highlight_only:
            conditions.append(FieldCondition(key="is_highlight", match=MatchValue(value=True)))
            
        if color_filter:
            conditions.append(FieldCondition(key="highlight_color", match=MatchValue(value=color_filter.lower())))
            
        search_filter = Filter(must=conditions) if conditions else None
        
        # API atualizada do Qdrant (v1.7+)
        results = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=query_vector,
            query_filter=search_filter,
            limit=limit,
            score_threshold=score_threshold if score_threshold > 0 else None
        )
        
        return [
            {
                "text": hit.payload.get("text", ""),
                "score": hit.score,
                **{k: v for k, v in hit.payload.items() if k != "text"}
            }
            for hit in results.points
        ]
    
    def delete_document(self, file_hash: str) -> int:
        """
        Remove todos os chunks de um documento específico.
        Retorna número de pontos removidos.
        """
        if not self.client:
            self.connect()
        
        # Contar antes
        before = self.client.count(
            collection_name=self.COLLECTION_NAME,
            count_filter=Filter(
                must=[FieldCondition(key="file_hash", match=MatchValue(value=file_hash))]
            )
        ).count
        
        # Deletar
        self.client.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="file_hash", match=MatchValue(value=file_hash))]
                )
            )
        )
        
        print(f"[Qdrant] Removidos {before} chunks do documento")
        return before
    
    def get_stats(self) -> dict:
        """Retorna estatísticas da collection."""
        if not self.client:
            self.connect()
        
        info = self.client.get_collection(self.COLLECTION_NAME)
        documents = self.get_indexed_documents()
        
        return {
            "points_count": info.points_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "status": info.status.value,
            "documents_count": len(documents)
        }
    
    def clear(self):
        """Remove todos os documentos da collection."""
        if not self.client:
            self.connect()
        
        self.client.delete_collection(self.COLLECTION_NAME)
        self._ensure_collection()
        print("[Qdrant] Collection limpa!")
    
    def close(self):
        """Fecha conexão com Qdrant."""
        if self.client:
            self.client.close()
            self.client = None


# Alias para compatibilidade
VectorDB = VectorStore
