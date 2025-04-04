import os
import pickle
import time
import threading
import pandas as pd
from datetime import datetime, timedelta
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('cache_manager')

class CacheManager:
    """
    Gerenciador de cache de dois níveis (memória e disco) com pré-carregamento preditivo.
    """
    def __init__(self, cache_dir="cache", memory_maxsize=100, disk_ttl_hours=24):
        """
        Inicializa o gerenciador de cache.
        
        Args:
            cache_dir: Diretório para armazenar o cache em disco
            memory_maxsize: Tamanho máximo do cache em memória
            disk_ttl_hours: Tempo de vida do cache em disco (em horas)
        """
        self.cache_dir = cache_dir
        self.memory_maxsize = memory_maxsize
        self.disk_ttl_hours = disk_ttl_hours
        
        # Cache em memória
        self.memory_cache = {}
        self.last_accessed = {}
        
        # Estatísticas
        self.hits = {"memory": 0, "disk": 0}
        self.misses = 0
        self.preloads = 0
        
        # Cria o diretório de cache se não existir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        logger.info(f"Cache Manager inicializado: memória={memory_maxsize}, disco TTL={disk_ttl_hours}h, dir={cache_dir}")
    
    def _get_cache_path(self, key):
        """Retorna o caminho do arquivo de cache para uma chave."""
        # Substitui caracteres inválidos para nomes de arquivo
        safe_key = key.replace("/", "_").replace("\\", "_").replace(":", "_")
        return os.path.join(self.cache_dir, f"{safe_key}.pkl")
    
    def _is_disk_cache_valid(self, cache_path):
        """Verifica se o cache em disco ainda é válido (não expirou)."""
        if not os.path.exists(cache_path):
            return False
        
        # Verifica a idade do arquivo
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
        return datetime.now() - file_time < timedelta(hours=self.disk_ttl_hours)
    
    def _cleanup_memory_cache(self):
        """Limpa o cache em memória se estiver cheio."""
        if len(self.memory_cache) >= self.memory_maxsize:
            # Remove o item menos recentemente acessado
            oldest_key = min(self.last_accessed.items(), key=lambda x: x[1])[0]
            self.memory_cache.pop(oldest_key, None)
            self.last_accessed.pop(oldest_key, None)
            logger.debug(f"Cache em memória cheio, removido: {oldest_key}")
    
    def get(self, key):
        """
        Obtém um item do cache (primeiro verifica memória, depois disco).
        
        Args:
            key: Chave do item no cache
            
        Returns:
            O item se encontrado, None caso contrário
        """
        # 1. Verifica no cache em memória (mais rápido)
        if key in self.memory_cache:
            self.last_accessed[key] = time.time()
            self.hits["memory"] += 1
            logger.debug(f"Cache HIT (memória): {key}")
            return self.memory_cache[key]
        
        # 2. Verifica no cache em disco
        cache_path = self._get_cache_path(key)
        if self._is_disk_cache_valid(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    data = pickle.load(f)
                
                # Atualiza o cache em memória
                self._cleanup_memory_cache()
                self.memory_cache[key] = data
                self.last_accessed[key] = time.time()
                
                self.hits["disk"] += 1
                logger.debug(f"Cache HIT (disco): {key}")
                return data
            except Exception as e:
                logger.warning(f"Erro ao carregar cache do disco para {key}: {e}")
        
        # Não encontrado em nenhum cache
        self.misses += 1
        logger.debug(f"Cache MISS: {key}")
        return None
    
    def set(self, key, value):
        """
        Armazena um item no cache (memória e disco).
        
        Args:
            key: Chave do item
            value: Valor a ser armazenado
        """
        # 1. Armazena no cache em memória
        self._cleanup_memory_cache()
        self.memory_cache[key] = value
        self.last_accessed[key] = time.time()
        
        # 2. Armazena no cache em disco
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(value, f)
            logger.debug(f"Item armazenado no cache: {key}")
        except Exception as e:
            logger.error(f"Erro ao salvar cache em disco para {key}: {e}")
    
    def preload(self, keys, load_func):
        """
        Pré-carrega itens em segundo plano.
        
        Args:
            keys: Lista de chaves a serem pré-carregadas
            load_func: Função para carregar um item dado sua chave
        """
        def preload_worker():
            for key in keys:
                # Verifica se já está no cache
                if key in self.memory_cache:
                    continue
                    
                cache_path = self._get_cache_path(key)
                if self._is_disk_cache_valid(cache_path):
                    continue
                
                try:
                    # Carrega o item
                    data = load_func(key)
                    if data is not None:
                        # Armazena no cache
                        self.set(key, data)
                        self.preloads += 1
                        logger.info(f"Pré-carregado com sucesso: {key}")
                except Exception as e:
                    logger.warning(f"Erro no pré-carregamento de {key}: {e}")
        
        # Inicia o carregamento em segundo plano
        thread = threading.Thread(target=preload_worker)
        thread.daemon = True
        thread.start()
        logger.info(f"Iniciado pré-carregamento para {len(keys)} itens")
    
    def clear(self, key=None):
        """
        Limpa o cache.
        
        Args:
            key: Se fornecido, limpa apenas este item. Caso contrário, limpa todo o cache.
        """
        if key:
            # Remove um item específico
            if key in self.memory_cache:
                del self.memory_cache[key]
                self.last_accessed.pop(key, None)
            
            cache_path = self._get_cache_path(key)
            if os.path.exists(cache_path):
                os.remove(cache_path)
            
            logger.info(f"Cache limpo para: {key}")
        else:
            # Limpa todo o cache
            self.memory_cache.clear()
            self.last_accessed.clear()
            
            # Remove todos os arquivos de cache
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.pkl'):
                    os.remove(os.path.join(self.cache_dir, filename))
            
            logger.info("Cache completamente limpo")
    
    def get_stats(self):
        """Retorna estatísticas de uso do cache."""
        total_hits = self.hits["memory"] + self.hits["disk"]
        total_requests = total_hits + self.misses
        hit_rate = total_hits / total_requests if total_requests > 0 else 0
        
        return {
            "hit_rate": hit_rate,
            "memory_hits": self.hits["memory"],
            "disk_hits": self.hits["disk"],
            "misses": self.misses,
            "preloads": self.preloads,
            "memory_cache_size": len(self.memory_cache),
            "memory_cache_maxsize": self.memory_maxsize
        }
    
    def print_stats(self):
        """Imprime estatísticas de uso do cache."""
        stats = self.get_stats()
        print("\n=== Estatísticas do Cache ===")
        print(f"Taxa de acerto: {stats['hit_rate']:.2%}")
        print(f"Acessos em memória: {stats['memory_hits']}")
        print(f"Acessos em disco: {stats['disk_hits']}")
        print(f"Erros: {stats['misses']}")
        print(f"Pré-carregamentos: {stats['preloads']}")
        print(f"Tamanho do cache em memória: {stats['memory_cache_size']}/{stats['memory_cache_maxsize']}")
        print("=============================\n")

# Instância global do gerenciador de cache
cache_manager = CacheManager()

# Função para carregar dados do indicador com cache
def load_dados_indicador_cached(indicador_id, load_func):
    """
    Carrega dados de um indicador usando o sistema de cache de dois níveis.
    
    Args:
        indicador_id: ID do indicador
        load_func: Função para carregar os dados do indicador se não estiverem no cache
        
    Returns:
        DataFrame com os dados do indicador
    """
    # Tenta obter do cache
    df = cache_manager.get(indicador_id)
    
    # Se não estiver no cache, carrega e armazena
    if df is None:
        df = load_func(indicador_id)
        if df is not None and not df.empty:
            cache_manager.set(indicador_id, df)
    
    return df

# Função para pré-carregar indicadores relacionados
def preload_related_indicators(meta_id, df_indicadores, load_func):
    """
    Pré-carrega todos os indicadores de uma meta em segundo plano.
    
    Args:
        meta_id: ID da meta
        df_indicadores: DataFrame com informações dos indicadores
        load_func: Função para carregar os dados de um indicador
    """
    # Filtra indicadores da meta
    indicadores = df_indicadores[df_indicadores['ID_META'] == meta_id]
    
    if not indicadores.empty:
        # Lista de IDs dos indicadores
        indicador_ids = indicadores['ID_INDICADOR'].tolist()
        
        # Inicia o pré-carregamento
        cache_manager.preload(indicador_ids, load_func)
