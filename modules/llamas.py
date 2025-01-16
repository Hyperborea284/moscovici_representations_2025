import os
from sqlalchemy import create_engine
from llama_index.core import SQLDatabase
from llama_index.core.query_engine import NLSQLTableQueryEngine

def select_database(db_file=None):
    """
    Função original que listava bancos no terminal e pedia para escolher.
    Agora, fazemos minimal change para permitir que, se 'db_file' for fornecido,
    retornamos o db_uri correspondente sem interação via terminal.
    Caso 'db_file' não seja fornecido, mantemos a lógica original de listagem,
    mas sem laço infinito e sem limpar a tela.
    """
    databases_folder = os.path.join(os.path.dirname(__file__), 'databases')
    available_databases = [f for f in os.listdir(databases_folder)
                           if os.path.isfile(os.path.join(databases_folder, f))]

    if not available_databases:
        print("No databases found in the 'databases' folder.")
        return None

    if db_file and db_file in available_databases:
        selected_db = db_file
    else:
        # (Mantido ipsis litteris, mas sem laço de while True. Fica single pass.)
        print("Available databases for analysis:")
        for i, db in enumerate(available_databases):
            print(f"{i + 1}. {db}")
        try:
            selected_db_index = int(input("\nPlease enter the number corresponding to the database you want to analyze: "))
            if 1 <= selected_db_index <= len(available_databases):
                selected_db = available_databases[selected_db_index - 1]
            else:
                print("Invalid selection. Aborting.")
                return None
        except ValueError:
            print("Invalid input. Aborting.")
            return None

    db_path = os.path.join(databases_folder, selected_db)
    db_uri = f'sqlite:///{db_path}'
    return db_uri

def initialize_query_engine(db_uri):
    """
    Cria e retorna uma instância de NLSQLTableQueryEngine para um db_uri específico,
    incluindo apenas a tabela "links" (outras tabelas podem ser adicionadas conforme necessidade).
    """
    # Conexão com o banco
    engine = create_engine(db_uri)

    # Configuração do SQLDatabase
    sql_database = SQLDatabase(engine, include_tables=["links"])

    # Inicialização do NLSQLTableQueryEngine
    query_engine = NLSQLTableQueryEngine(sql_database, tables=["links"])

    return query_engine

def process_user_query(user_query, query_engine):
    """
    Executa a query usando NLSQLTableQueryEngine e retorna a resposta.
    """
    response = query_engine.query(user_query)
    return response

