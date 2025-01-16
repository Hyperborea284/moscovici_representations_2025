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
    Caso o DB não exista, cria as tabelas necessárias.
    Cada execução do 'Enviar conteúdo' deve gerar um DB com o nome do timestamp.
    Ao inicializar, caso o arquivo não exista, cria as tabelas.
    """
    if not db_path:
        return

    if not os.path.isfile(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Tabela que registra todos os conteúdos inseridos (arquivo, texto copiado, links)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conteudos_ingestao (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fonte TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            # Tabela para links raspados (um caso particular de ingestão)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS links_raspados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    link TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            # Tabela para guardar as entidades, localidades, tópicos e resumos (entity_finder)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entity_finder (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            # Tabela para a timeline (prompt + xml retornado)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS timeline (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            # Tabela para a análise de sentimentos (caminho dos gráficos, etc.)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analise_sentimentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            # Tabela para as representações sociais (gráficos, tabelas, etc.)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS representacoes_sociais (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    timestamp TEXT NOT NULL
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

            # >>>>> NOVA TABELA PARA CENÁRIOS <<<<<
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cenarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT NOT NULL,
                    topicos TEXT NOT NULL,
                    resumo TEXT NOT NULL,
                    cenarios TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            conn.commit()
        finally:
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

def insert_content_ingestao(db_path: str, fonte: str, conteudo: str):
    """
    Insere um registro na tabela de conteúdos de ingestão, calculando o hash do conteúdo.
    """
    if not db_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        hash_value = calculate_hash(conteudo)
        current_ts = time.strftime('%Y%m%d_%H%M%S')
        query = """
            INSERT INTO conteudos_ingestao (fonte, conteudo, hash, timestamp)
            VALUES (?, ?, ?, ?)
        """
        cursor.execute(query, (fonte, conteudo, hash_value, current_ts))
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
            INSERT INTO links_raspados (link, conteudo, hash, timestamp)
            VALUES (?, ?, ?, ?)
        """
        cursor.execute(query, (link, conteudo, hash_value, current_ts))
        conn.commit()
    finally:
        conn.close()

def memoize_result(db_path: str, table_name: str, unique_content: str):
    """
    Função de memoização para "envelopar" processamentos de scripts/classes/funções.
    Recebe o conteúdo (por exemplo, prompt, texto, etc.), verifica seu hash,
    e consulta a tabela correspondente para ver se já foi processado.
    Caso exista, retorna o conteúdo do DB; se não, retorna None.
    """
    if not db_path:
        return None

    hash_val = calculate_hash(unique_content)
    existing = check_if_exists(db_path, table_name, hash_val)
    if existing:
        return existing  # Conteúdo já memoizado
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
    Exemplo de registro de chamada à API (pode ser usado no entity_finder ou outro script).
    """
    if not db_path:
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # O hash pode se basear nos parâmetros + api_name
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

# >>>>> NOVA FUNÇÃO DE EXEMPLO PARA CENÁRIOS <<<<<
def insert_cenarios(db_path: str, topicos: str, resumo: str, cenarios_json: str):
    """
    Inserção específica na tabela 'cenarios', com colunas (hash, topicos, resumo, cenarios, timestamp).
    Assim armazenamos cada novo conjunto de cenários gerados, evitando duplicação.
    """
    if not db_path:
        return

    # Para fins de memoização, construímos a string-base a partir de topicos+resumo+cenarios_json
    combined_str = f"{topicos}|{resumo}|{cenarios_json}"
    hash_val = calculate_hash(combined_str)

    # Verificamos se já existe registro idêntico
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        current_ts = time.strftime('%Y%m%d_%H%M%S')

        # Verificar se o hash já existe
        cursor.execute("SELECT id FROM cenarios WHERE hash = ?", (hash_val,))
        row = cursor.fetchone()
        if row:
            print("Cenários já registrados anteriormente. (memo)")
        else:
            # Inserir
            cursor.execute("""
                INSERT INTO cenarios (hash, topicos, resumo, cenarios, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (hash_val, topicos, resumo, cenarios_json, current_ts))
            conn.commit()
            print("Cenários inseridos com sucesso!")
    finally:
        conn.close()
