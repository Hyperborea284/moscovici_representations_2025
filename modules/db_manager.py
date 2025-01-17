import os
import sqlite3
import hashlib
import time

def get_db_path(db_folder: str, timestamp: str) -> str:
    """
    Gera o caminho completo para o arquivo de banco de dados com base em um timestamp.
    Caso o timestamp não seja fornecido, retorna None.
    """
    if not timestamp:
        return None
    os.makedirs(db_folder, exist_ok=True)
    return os.path.join(db_folder, f"{timestamp}.db")

def create_db_if_not_exists(db_path: str):
    """
    Caso o DB não exista, cria as tabelas necessárias e adiciona colunas se preciso.
    Cada execução do 'Enviar conteúdo' deve gerar um DB com o nome do timestamp.
    """
    if not db_path:
        return

    new_db = not os.path.isfile(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if new_db:
        # Tabela que registra todos os conteúdos inseridos (arquivo, texto copiado, links)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conteudos_ingestao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fonte TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                arquivos_enviados TEXT,
                texto_copiado TEXT,
                hash TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        # Tabela para links raspados (um caso particular de ingestão)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS links_raspados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                links TEXT NOT NULL,
                conteudos TEXT NOT NULL,
                hash TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        # Tabela para guardar as entidades, localidades, tópicos e resumos (entity_finder)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entity_finder (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT NOT NULL,
                prompt TEXT,
                texto_analisado TEXT,
                topicos_principais TEXT,
                resumo TEXT,
                pessoas_organizacoes TEXT,
                dados_mapa TEXT,
                timestamp TEXT NOT NULL,
                conteudo TEXT
            )
        """)

        # Tabela para a timeline
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT NOT NULL,
                prompt TEXT,
                texto_analisado TEXT,
                xml_final TEXT,
                timestamp TEXT NOT NULL,
                conteudo TEXT
            )
        """)

        # Tabela para a análise de sentimentos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analise_sentimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT NOT NULL,
                texto_analisado TEXT,
                caminhos_imagens TEXT,
                timestamp TEXT NOT NULL,
                conteudo TEXT
            )
        """)

        # Tabela para as representações sociais
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS representacoes_sociais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT NOT NULL,
                texto_analisado TEXT,
                filtros_utilizados TEXT,
                caminhos_imagens TEXT,
                conteudos_tabelas TEXT,
                timestamp TEXT NOT NULL,
                conteudo TEXT
            )
        """)

        # Tabela geral para armazenar objetos de scripts adicionais
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS outros_objetos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_origem TEXT NOT NULL,
                hash TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        # Tabela opcional para armazenar chamadas a APIs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_name TEXT NOT NULL,
                parametros TEXT NOT NULL,
                hash TEXT NOT NULL,
                resposta TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        # Tabela 'contexto'
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contexto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT NOT NULL,
                texto_analisado TEXT,
                prompt TEXT,
                topicos TEXT,
                resumo TEXT,
                conteudos_tabelas TEXT,
                timestamp TEXT NOT NULL,
                conteudo TEXT
            )
        """)

    else:
        # Se o DB já existe, garantimos as colunas
        try:
            cursor.execute("ALTER TABLE conteudos_ingestao ADD COLUMN arquivos_enviados TEXT")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE conteudos_ingestao ADD COLUMN texto_copiado TEXT")
        except:
            pass

        # Tabelas de análise:
        # entity_finder
        for col in ["prompt", "texto_analisado", "topicos_principais", "resumo",
                    "pessoas_organizacoes", "dados_mapa", "conteudo"]:
            try:
                cursor.execute(f"ALTER TABLE entity_finder ADD COLUMN {col} TEXT")
            except:
                pass

        # timeline
        for col in ["prompt", "texto_analisado", "xml_final", "conteudo"]:
            try:
                cursor.execute(f"ALTER TABLE timeline ADD COLUMN {col} TEXT")
            except:
                pass

        # analise_sentimentos
        for col in ["texto_analisado", "caminhos_imagens", "conteudo"]:
            try:
                cursor.execute(f"ALTER TABLE analise_sentimentos ADD COLUMN {col} TEXT")
            except:
                pass

        # representacoes_sociais
        for col in ["texto_analisado", "filtros_utilizados", "caminhos_imagens", "conteudos_tabelas", "conteudo"]:
            try:
                cursor.execute(f"ALTER TABLE representacoes_sociais ADD COLUMN {col} TEXT")
            except:
                pass

        try:
            cursor.execute("ALTER TABLE cenarios RENAME TO contexto")
        except:
            pass

        for col in ["texto_analisado", "prompt", "topicos", "resumo", "conteudos_tabelas", "conteudo"]:
            try:
                cursor.execute(f"ALTER TABLE contexto ADD COLUMN {col} TEXT")
            except:
                pass

    conn.commit()
    conn.close()

def calculate_hash(content: str) -> str:
    """
    Calcula um hash SHA256 para o conteúdo fornecido.
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def check_if_exists(db_path: str, table_name: str, hash_value: str) -> str:
    """
    Verifica se um hash já está registrado na tabela especificada.
    Se existir, retorna o conteúdo; caso contrário, retorna None.
    """
    if not db_path or not os.path.isfile(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        query = f"SELECT conteudo FROM {table_name} WHERE hash = ?"
        cursor.execute(query, (hash_value,))
        row = cursor.fetchone()
        if row:
            return row[0]  # Conteúdo já existente
        else:
            return None
    finally:
        conn.close()

def insert_content(db_path: str, table_name: str, hash_value: str, content: str):
    """
    Insere conteúdo em uma tabela, associando um hash e o timestamp atual.
    """
    if not db_path:
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        current_ts = time.strftime('%Y%m%d_%H%M%S')
        query = f"INSERT INTO {table_name} (hash, conteudo, timestamp) VALUES (?, ?, ?)"
        cursor.execute(query, (hash_value, content, current_ts))
        conn.commit()
    finally:
        conn.close()

def insert_content_ingestao(db_path: str, fonte: str, conteudo: str,
                            arquivos_enviados: str = None,
                            texto_copiado: str = None):
    """
    Insere um registro na tabela de conteúdos de ingestão.
    """
    if not db_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        hash_value = calculate_hash(conteudo)
        current_ts = time.strftime('%Y%m%d_%H%M%S')
        query = """
            INSERT INTO conteudos_ingestao
            (fonte, conteudo, arquivos_enviados, texto_copiado, hash, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (fonte, conteudo, arquivos_enviados or None,
                               texto_copiado or None, hash_value, current_ts))
        conn.commit()
    finally:
        conn.close()

def insert_link_raspado(db_path: str, link: str, conteudo: str):
    """
    Insere um registro na tabela de links_raspados, calculando o hash do texto obtido.
    """
    if not db_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        hash_value = calculate_hash(conteudo)
        current_ts = time.strftime('%Y%m%d_%H%M%S')
        query = """
            INSERT INTO links_raspados (links, conteudos, hash, timestamp)
            VALUES (?, ?, ?, ?)
        """
        cursor.execute(query, (link, conteudo, hash_value, current_ts))
        conn.commit()
    finally:
        conn.close()

def memoize_result(db_path: str, table_name: str, unique_content: str):
    """
    Verifica se o 'unique_content' já foi processado (hash) e retornado.
    """
    if not db_path:
        return None

    hash_val = calculate_hash(unique_content)
    existing = check_if_exists(db_path, table_name, hash_val)
    if existing:
        return existing
    return None

def store_memo_result(db_path: str, table_name: str, unique_content: str, processed_output: str):
    """
    Armazena o resultado de um processamento (processed_output) relacionado ao
    conteúdo (unique_content), caso ainda não esteja no banco.
    """
    if not db_path:
        return

    hash_val = calculate_hash(unique_content)
    existing = check_if_exists(db_path, table_name, hash_val)
    if not existing:
        insert_content(db_path, table_name, hash_val, processed_output)

def insert_api_call(db_path: str, api_name: str, parametros: str, resposta: str):
    """
    Exemplo de registro de chamada à API.
    """
    if not db_path:
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        hash_value = calculate_hash(api_name + parametros)
        current_ts = time.strftime('%Y%m%d_%H%M%S')
        query = """
            INSERT INTO api_calls (api_name, parametros, hash, resposta, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """
        cursor.execute(query, (api_name, parametros, hash_value, resposta, current_ts))
        conn.commit()
    finally:
        conn.close()

def list_existing_dbs(db_folder: str) -> list:
    """
    Lista todos os arquivos .db disponíveis no diretório especificado.
    """
    if not os.path.isdir(db_folder):
        return []
    return [f for f in os.listdir(db_folder) if f.endswith('.db')]

# >>>>> Funções de salvamento (convergência das abas) <<<<<

def save_entidades(db_path: str, prompt: str, texto_analisado: str,
                   topicos: list, resumo: str, pessoas: list, dados_mapa: str):
    """
    Salva as entidades e localidades na tabela entity_finder.
    """
    if not db_path:
        return
    if not (prompt or topicos or resumo):
        # Mesmo se texto_analisado estiver vazio, forçamos salvamento se prompt ou topicos existirem
        pass
    conteudo_base = f"prompt:{prompt}\ntexto:{texto_analisado}\ntopicos:{topicos}\nresumo:{resumo}"
    hash_val = calculate_hash(conteudo_base)
    current_ts = time.strftime('%Y%m%d_%H%M%S')
    topicos_str = ', '.join(topicos) if isinstance(topicos, list) else str(topicos)
    pessoas_str = str(pessoas)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
        INSERT INTO entity_finder
        (hash, prompt, texto_analisado, topicos_principais, resumo, pessoas_organizacoes, dados_mapa, conteudo, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(query, (
        hash_val, prompt, texto_analisado, topicos_str, resumo,
        pessoas_str, dados_mapa, conteudo_base, current_ts
    ))
    conn.commit()
    conn.close()

def save_timeline(db_path: str, prompt: str, texto_analisado: str, xml_final: str):
    if not db_path:
        return
    conteudo_base = f"prompt:{prompt}\ntexto:{texto_analisado}\nxml:{xml_final}"
    hash_val = calculate_hash(conteudo_base)
    current_ts = time.strftime('%Y%m%d_%H%M%S')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = """
        INSERT INTO timeline
        (hash, prompt, texto_analisado, xml_final, conteudo, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    cursor.execute(query, (hash_val, prompt, texto_analisado, xml_final, conteudo_base, current_ts))
    conn.commit()
    conn.close()

def save_sentimentos(db_path: str, texto_analisado: str, caminhos_imagens: str):
    if not db_path:
        return
    conteudo_base = f"sentimentos base do texto:\n{texto_analisado}"
    hash_val = calculate_hash(conteudo_base)
    current_ts = time.strftime('%Y%m%d_%H%M%S')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = """
        INSERT INTO analise_sentimentos
        (hash, texto_analisado, caminhos_imagens, conteudo, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """
    cursor.execute(query, (hash_val, texto_analisado, caminhos_imagens, conteudo_base, current_ts))
    conn.commit()
    conn.close()

def save_representacao_social(db_path: str, texto_analisado: str,
                              filtros_utilizados: str, caminhos_imagens: str,
                              conteudos_tabelas: str):
    if not db_path:
        return
    conteudo_base = f"RepresentacaoSocial:\n{texto_analisado}\nFiltros:{filtros_utilizados}"
    hash_val = calculate_hash(conteudo_base)
    current_ts = time.strftime('%Y%m%d_%H%M%S')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = """
        INSERT INTO representacoes_sociais
        (hash, texto_analisado, filtros_utilizados, caminhos_imagens, conteudos_tabelas, conteudo, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(query, (
        hash_val, texto_analisado, filtros_utilizados,
        caminhos_imagens, conteudos_tabelas,
        conteudo_base, current_ts
    ))
    conn.commit()
    conn.close()

def save_contexto(db_path: str, texto_analisado: str, prompt: str,
                  topicos: str, resumo: str, conteudos_tabelas: str):
    if not db_path:
        return
    conteudo_base = f"contexto:\n{texto_analisado}\nprompt:{prompt}\ntopicos:{topicos}\nresumo:{resumo}"
    hash_val = calculate_hash(conteudo_base)
    current_ts = time.strftime('%Y%m%d_%H%M%S')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = """
        INSERT INTO contexto
        (hash, texto_analisado, prompt, topicos, resumo, conteudos_tabelas, conteudo, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(query, (
        hash_val, texto_analisado, prompt, topicos, resumo,
        conteudos_tabelas, conteudo_base, current_ts
    ))
    conn.commit()
    conn.close()
