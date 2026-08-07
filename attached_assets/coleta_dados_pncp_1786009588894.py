# import requests
# import time
# import logging
# import json
# import hashlib
# from datetime import datetime
# from pymongo import MongoClient, ASCENDING
# from pymongo.errors import OperationFailure

import requests
import time
import logging
import json
import hashlib
import random
from datetime import datetime
from pymongo import MongoClient, ASCENDING
from pymongo.errors import OperationFailure

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB = "inteligencia_licitacoes"

UF_ALVO = "CE"
MODALIDADE = 6  # 6 = Pregão Eletrônico

# PERÍODO DEFINIDO (Coleta pelo período, não dia a dia)
DATA_INICIO = "2025-01-01"
DATA_FIM = "2025-01-31"

BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

# Lista de User-Agents realistas e modernos para rotação
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
]

# ==============================================================================
# FUNÇÕES AUXILIARES
# ==============================================================================

def gerar_headers_aleatorios():
    """Gera um dicionário de headers com User-Agent aleatório para cada requisição."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache"
    }

# ==============================================================================
# BANCO DE DADOS (MongoDB)
# ==============================================================================
class BancoMongo:
    def __init__(self, uri: str, db_name: str):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self._criar_indices()
        logging.info(f"✅ Conectado ao MongoDB: {uri} | DB: {db_name}")

    def _criar_indices(self):
        # 1. LIMPEZA TOTAL: Remove TODOS os índices antigos para evitar conflito com índices "fantasmas" (ex: controle_pncp_1)
        try:
            self.db.licitacoes.drop_indexes()
            logging.info("✅ Índices antigos removidos com sucesso para evitar conflitos.")
        except Exception:
            pass

        # 2. CRIAÇÃO LIMPA: Cria o índice único com o nome e campo exatos
        self.db.licitacoes.create_index(
            [("numeroControlePNCP", ASCENDING)], 
            unique=True, 
            name="idx_numero_controle_pncp_unico"
        )

    def upsert_licitacao(self, dados: dict):
        # Tenta pegar o ID oficial. Se não existir, gera um hash MD5 único baseado no conteúdo
        controle_id = dados.get("numeroControlePNCP") or dados.get("numeroControlePncp")
        
        if not controle_id:
            controle_id = hashlib.md5(json.dumps(dados, sort_keys=True).encode('utf-8')).hexdigest()
        
        # Garante que o campo exista no dicionário com o nome EXATO do índice criado
        dados["numeroControlePNCP"] = str(controle_id)
        
        try:
            self.db.licitacoes.update_one(
                {"numeroControlePNCP": dados["numeroControlePNCP"]},
                {"$set": dados},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Erro ao salvar licitação {controle_id}: {e}")

# ==============================================================================
# SESSÃO HTTP
# ==============================================================================
# def criar_sessao():
#     sessao = requests.Session()
#     sessao.headers.update({
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
#         "Accept": "application/json, text/plain, */*",
#         "Accept-Language": "pt-BR,pt;q=0.9",
#         "Connection": "keep-alive"
#     })
#     return sessao

def criar_sessao():
    # Criamos a sessão sem headers fixos, pois eles serão atualizados dinamicamente
    sessao = requests.Session()
    
    # Configuração de Retry para resiliência de rede
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    retry_strategy = Retry(
        total=2,
        backoff_factor=5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    sessao.mount("http://", adapter)
    sessao.mount("https://", adapter)
    
    return sessao


# ==============================================================================
# NÚCLEO DA COLETA (Período Definido + Session com Params)
# ==============================================================================
def main():
    banco = BancoMongo(MONGO_URI, MONGO_DB)
    sessao = criar_sessao()
    
    # Converte datas para o formato AAAAMMDD exigido pela API
    data_ini_str = datetime.strptime(DATA_INICIO, "%Y-%m-%d").strftime("%Y%m%d")
    data_fim_str = datetime.strptime(DATA_FIM, "%Y-%m-%d").strftime("%Y%m%d")
    
    logging.info("="*70)
    logging.info("🚀 COLETOR PNCP + MONGODB (Período Definido)")
    logging.info(f"Alvo: {UF_ALVO} | Modalidade: {MODALIDADE}")
    logging.info(f"Período: {DATA_INICIO} a {DATA_FIM}")
    logging.info("="*70)
    
    # PARÂMETROS EXATOS (Sem o campo 'uf' para evitar sobrecarga no servidor)
    params = {
        "dataInicial": data_ini_str,
        "dataFinal": data_fim_str,
        "codigoModalidadeContratacao": MODALIDADE,
        "tamanhoPagina": 20,  # Tamanho validado que evita erro 500
        "pagina": 1
    }
    
    total_geral = 0
    pagina = 1
    tentativas_falha = 0
    
    # Limite de segurança de páginas para o período definido
    while pagina <= 100:  
        try:
            params["pagina"] = pagina

            _URL = BASE_URL + f'?dataInicial={data_ini_str}&dataFinal={data_fim_str}&codigoModalidadeContratacao={MODALIDADE}&tamanhoPagina={20}&pagina={pagina}'

            # ==========================================================================
            # ATUALIZA HEADERS ALEATÓRIOS ANTES DE CADA REQUISIÇÃO
            # ==========================================================================
            sessao.headers.update(gerar_headers_aleatorios())
            
            # USO DIRETO DA SESSÃO COM PARAMS (O requests cuida da formação correta da URL)
            # response = sessao.get(BASE_URL, params=params, timeout=60)
            response = sessao.get(_URL, timeout=60)
            
            if response.status_code == 204:
                logging.info("➖ Nenhum registro neste período (204 No Content).")
                break
                
            if response.status_code == 429:
                logging.warning(f"⚠️ Rate Limit (429) na pág {pagina}. Aguardando 30s...")
                time.sleep(30)
                tentativas_falha += 1
                if tentativas_falha >= 3:
                    logging.error("❌ Rate limit persistente. Encerrando coleta.")
                    break
                continue  # Tenta a mesma página de novo
                
            if response.status_code == 500:
                tentativas_falha += 1
                if tentativas_falha < 3:
                    logging.warning(f"⚠️ Servidor retornou 500 na pág {pagina}. Aguardando 15s...")
                    time.sleep(15)
                    continue
                else:
                    logging.error(f"❌ Servidor instável (500 persistente). Encerrando coleta.")
                    break
            
            response.raise_for_status()
            dados = response.json()
            itens = dados.get("data", [])
            
            if not itens:
                logging.info("➖ Fim dos registros para este período.")
                break
                
            # FILTRAGEM LOCAL POR UF E SALVAMENTO NO MONGODB
            registros_salvos_pagina = 0
            for item in itens:
                banco.upsert_licitacao(item)
                registros_salvos_pagina += 1

            # for item in itens:
            #     uf_item = item.get("ufSigla") or (item.get("unidadeOrgao") or {}).get("ufSigla") or item.get("uf")
            #     if uf_item and uf_item.upper() == UF_ALVO:
            #         banco.upsert_licitacao(item)
            #         registros_salvos_pagina += 1
            
            # logging.info(f"📄 Pág {pagina}: {len(itens)} brutos, {registros_salvos_pagina} do {UF_ALVO} salvos no Mongo.")
            logging.info(f"📄 Pág {pagina}: {len(itens)} brutos, {registros_salvos_pagina} salvos no Mongo.")
            total_geral += registros_salvos_pagina
            
            if dados.get("paginasRestantes", 0) == 0:
                logging.info("✅ Todas as páginas deste período foram processadas.")
                break
                
            pagina += 1
            tentativas_falha = 0  # Reseta contador de falhas em caso de sucesso
            # time.sleep(2.0)  # Pausa gentil entre páginas
            # ==========================================================================
            # DELAY ALEATÓRIO ENTRE 2.5 E 5 SEGUNDOS (Conforme solicitado)
            # ==========================================================================
            delay_aleatorio = random.uniform(2.5, 5.0)
            time.sleep(delay_aleatorio)
            
        except requests.exceptions.ReadTimeout:
            logging.warning(f"⏱️ Read Timeout na pág {pagina}. Aguardando 20s...")
            time.sleep(20)
            tentativas_falha += 1
            if tentativas_falha >= 3:
                logging.error("❌ Timeout persistente. Encerrando coleta.")
                break
        except requests.exceptions.RequestException as e:
            logging.warning(f"⚠️ Erro de rede na pág {pagina}: {e}. Aguardando 10s...")
            time.sleep(10)
            tentativas_falha += 1
            if tentativas_falha >= 3:
                break

    logging.info("="*70)
    # logging.info(f"✅ CONCLUÍDO! Total de licitações do {UF_ALVO} salvas no MongoDB: {total_geral}")
    logging.info(f"✅ CONCLUÍDO! Total de licitações salvas no MongoDB: {total_geral}")
    logging.info(f"💾 Verifique no MongoDB Compass: DB '{MONGO_DB}' -> Collection 'licitacoes'")
    logging.info("="*70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("\n⚠️ Coleta interrompida manualmente pelo usuário.")