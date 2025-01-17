import os
import time
import sys
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from flask import Flask, request, render_template, jsonify

from dotenv import load_dotenv

# Módulos do projeto
from modules.sent_bayes import SentimentAnalyzer
from modules.representacao_social import process_representacao_social
from modules.goose_scraper import scrape_links
from modules.timeline_generator import TimelineGenerator, TimelineParser
from modules.entity_finder import EntityClassifier, process_text
from modules.prospect import TextProcessor, ScenarioClassifier


# db_manager
from modules.db_manager import (
    get_db_path,
    create_db_if_not_exists,
    insert_content_ingestao,
    insert_link_raspado,
    memoize_result,
    store_memo_result,
    list_existing_dbs,
    save_entidades,
    save_timeline,
    save_sentimentos,
    save_representacao_social,
    save_contexto
)

# >>>> Início das Funções Auxiliares adicionadas <<<<

import sqlite3

def fetch_last_ingested_content(db_path: str):
    """
    Recupera o último conteúdo inserido na tabela conteudos_ingestao,
    ordenando pelo id desc, para utilizar em análises subsequentes.
    """
    if not db_path or not os.path.isfile(db_path):
        return None
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT conteudo
            FROM conteudos_ingestao
            ORDER BY id DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return {"conteudo": row[0]}
    finally:
        conn.close()
    return None

# >>>> Fim das Funções Auxiliares adicionadas <<<<

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("A chave da API não foi encontrada no .env.")

serp_api_key = os.getenv("SERP_API_KEY")
if not serp_api_key:
    raise ValueError("A chave da API não foi encontrada no .env.")

app = Flask(__name__)

UPLOAD_FOLDER = './static/generated'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_FOLDER = './static/dbs'
os.makedirs(DB_FOLDER, exist_ok=True)

entity_classifier = EntityClassifier(openai_api_key, serp_api_key)

# Mantido: conteúdo compartilhado global, mas sem mais uso para texto
shared_content = {
    "text": None,          # <--- Não mais utilizado
    "html_fixed": None,    # <--- Não mais utilizado
    "html_dynamic": None,  # <--- Não mais utilizado
    "algorithm": None,     # <--- Não mais utilizado
    "bad_links": [],
    "timeline_file": None,
    "entities": None,
    "timestamp": None,
    "counts": None,
    "selected_db": None,

    # Campos para registro cumulativo:
    "prompt": None,
    "topicos": None,
    "resumo": None,
    "pessoas_organizacoes": None,
    "dados_mapa": None,
    "xml_final": None,
    "caminhos_imagens": None,
    "filtros_utilizados": None,
    "conteudos_tabelas": None
}

sentiment_analyzer = SentimentAnalyzer(output_dir=UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html', shared_content=shared_content)

@app.route('/select_db', methods=['GET', 'POST'])
def select_db():
    """
    Lista e seleciona o DB no menu dropdown.
    """
    db_files = list_existing_dbs(DB_FOLDER)

    if request.method == 'POST':
        selected_db = request.form.get('db_name', '')
        if selected_db and selected_db in db_files:
            shared_content["selected_db"] = os.path.join(DB_FOLDER, selected_db)
            return jsonify({"status": "success", "selected_db": selected_db})
        else:
            return jsonify({"error": "DB inválido ou inexistente"}), 400

    return jsonify({"db_files": db_files})

@app.route('/delete_db', methods=['POST'])
def delete_db():
    db_name = request.form.get('db_name', '')
    if not db_name:
        return jsonify({"error": "Nenhum DB fornecido"}), 400
    full_path = os.path.join(DB_FOLDER, db_name)
    if not os.path.isfile(full_path):
        return jsonify({"error": "DB não encontrado"}), 404
    try:
        os.remove(full_path)
        if shared_content.get("selected_db") == full_path:
            shared_content["selected_db"] = None
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/save_to_db', methods=['POST'])
def save_to_db():
    """
    Salva os dados atuais (shared_content) no DB selecionado,
    caso existam dados para cada aba.
    """
    db_path = shared_content.get("selected_db")
    if not db_path:
        return jsonify({"error": "Nenhum DB selecionado"}), 400

    if not os.path.isfile(db_path):
        return jsonify({"error": "O arquivo de DB não existe"}), 400

    # Se existirem entidades
    if shared_content.get("entities"):
        save_entidades(
            db_path=db_path,
            prompt=shared_content.get("prompt", ""),
            texto_analisado="",  # Texto não mais usado via cache
            topicos=shared_content["entities"].get("topicos", []),
            resumo=shared_content["entities"].get("resumo", ""),
            pessoas=shared_content["entities"].get("pessoas", []),
            dados_mapa=shared_content["entities"].get("map_html", "")
        )

    # Se existir timeline
    if shared_content.get("timeline_file"):
        save_timeline(
            db_path=db_path,
            prompt=shared_content.get("prompt", ""),
            texto_analisado="",  # Texto não mais usado via cache
            xml_final=shared_content.get("xml_final", "")
        )

    # Se existir análise de sentimentos
    # (html_dynamic e html_fixed não mais mantidos em shared_content)
    if shared_content.get("counts"):
        save_sentimentos(
            db_path=db_path,
            texto_analisado="",  # Texto não mais usado via cache
            caminhos_imagens="(imagens geradas em pasta static, se houver)"
        )

    # Se existir representação social
    if shared_content.get("filtros_utilizados") or shared_content.get("conteudos_tabelas"):
        save_representacao_social(
            db_path=db_path,
            texto_analisado="",  # Texto não mais usado via cache
            filtros_utilizados=shared_content.get("filtros_utilizados", ""),
            caminhos_imagens=shared_content.get("caminhos_imagens", ""),
            conteudos_tabelas=shared_content.get("conteudos_tabelas", "")
        )

    # Se existir cenários
    if shared_content.get("topicos") or shared_content.get("resumo"):
        save_contexto(
            db_path=db_path,
            texto_analisado="",  # Texto não mais usado via cache
            prompt=shared_content.get("prompt", ""),
            topicos=shared_content.get("topicos", ""),
            resumo=shared_content.get("resumo", ""),
            conteudos_tabelas=shared_content.get("conteudos_tabelas", "")
        )

    return jsonify({"status": "success", "message": "Dados salvos no DB com sucesso."})

@app.route('/ingest_content', methods=['POST'])
def ingest_content():
    """
    Ingestão de texto via arquivo .txt ou texto copiado.
    Agora o texto não é mais armazenado em shared_content,
    e sim diretamente no DB. Em seguida, é lido do DB para análise.
    """
    db_path = shared_content.get("selected_db")
    if not db_path or not os.path.isfile(db_path):
        return jsonify({"error": "Nenhum DB válido selecionado"}), 400

    uploaded_file = request.files.get('file')
    text_input = request.form.get('text', '').strip()
    links_input = request.form.get('links', '').strip()

    sources_used = []
    if uploaded_file and uploaded_file.filename:
        sources_used.append('file')
    if text_input:
        sources_used.append('text')
    if links_input:
        sources_used.append('links')

    if len(sources_used) > 1:
        return jsonify({"status": "conflict", "sources": sources_used})

    final_text = ""
    fonte_usada = ""

    # Ingestão de arquivo
    if uploaded_file and uploaded_file.filename:
        fonte_usada = "arquivo"
        final_text = uploaded_file.read().decode('utf-8', errors='replace')
        insert_content_ingestao(
            db_path, fonte_usada, final_text,
            arquivos_enviados=final_text,
            texto_copiado=None
        )

    # Ingestão de texto copiado
    elif text_input:
        fonte_usada = "texto_copiado"
        final_text = text_input
        insert_content_ingestao(
            db_path, fonte_usada, final_text,
            arquivos_enviados=None,
            texto_copiado=final_text
        )

    # Ingestão de links (nesta rota não devíamos, mas se chegar aqui):
    elif links_input:
        return jsonify({"error": "Use /ingest_links para enviar links."}), 400

    if not final_text.strip():
        return jsonify({"error": "Nenhum conteúdo fornecido"}), 400

    # Lemos imediatamente do DB para prosseguir a análise
    last_entry = fetch_last_ingested_content(db_path)
    if not last_entry:
        return jsonify({"error": "Erro ao recuperar conteúdo do DB"}), 500

    analysis_text = last_entry["conteudo"]

    # Executa análise de sentimentos
    try:
        html_fixed, html_dynamic, num_pars, num_sents, _ = sentiment_analyzer.execute_analysis_text(analysis_text)
        # Retornamos no JSON (mas não armazenamos mais em shared_content)
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Erro durante a ingestão de conteúdo: {e}")
        return jsonify({"error": "Erro ao processar o conteúdo"}), 500

@app.route('/ingest_links', methods=['POST'])
def ingest_links():
    """
    Ingestão de texto por links, com raspagem e subsequente análise de sentimentos,
    armazenando o conteúdo somente no DB.
    """
    db_path = shared_content.get("selected_db")
    if not db_path or not os.path.isfile(db_path):
        return jsonify({"error": "Nenhum DB válido selecionado"}), 400

    links_text = request.form.get('links', '')
    if not links_text.strip():
        return jsonify({"error": "Nenhum link fornecido"}), 400

    links_list = [l.strip() for l in links_text.splitlines() if l.strip()]
    if not links_list:
        return jsonify({"error": "Nenhum link válido fornecido"}), 400

    try:
        combined_text, bad_links = scrape_links(links_list)
    except Exception as e:
        print(f"Erro durante raspagem de links: {e}")
        return jsonify({"error": f"Erro ao raspar links: {str(e)}"}), 500

    # Registrar cada link e seu conteúdo
    # Observação: nesta versão minimalista, todos os links raspados inserem o mesmo 'combined_text'
    # mas seria possível dividir.
    for link in links_list:
        insert_link_raspado(db_path, link, combined_text)

    if not combined_text.strip():
        return jsonify({"error": "Não foi possível obter conteúdo dos links"}), 400

    # Também registramos na tabela conteudos_ingestao (fonte='links'):
    insert_content_ingestao(
        db_path, "links", combined_text,
        arquivos_enviados=None,
        texto_copiado=None
    )

    # Lemos do DB para análise
    last_entry = fetch_last_ingested_content(db_path)
    if not last_entry:
        return jsonify({"error": "Erro ao recuperar conteúdo do DB"}), 500

    analysis_text = last_entry["conteudo"]

    # Executa análise de sentimentos
    try:
        html_fixed, html_dynamic, num_pars, num_sents, _ = sentiment_analyzer.execute_analysis_text(analysis_text)
        return jsonify({
            "status": "success",
            "bad_links": bad_links,
            "html_fixed": {
                "analyzedText": html_fixed,
                "timestamp": time.strftime('%Y%m%d_%H%M%S'),
                "counts": f"Parágrafos: {num_pars}, Frases: {num_sents}",
            },
            "html_dynamic": html_dynamic
        })
    except Exception as e:
        print(f"Erro durante a ingestão de conteúdo via links: {e}")
        return jsonify({"error": "Erro ao processar o conteúdo"}), 500

@app.route('/reset_content', methods=['POST'])
def reset_content():
    """
    Zera somente o shared_content, exceto pelo selected_db. 
    Observando que agora o texto está no DB, não no cache.
    """
    global shared_content
    old_db = shared_content.get("selected_db")
    shared_content = {
        "text": None,
        "html_fixed": None,
        "html_dynamic": None,
        "algorithm": None,
        "bad_links": [],
        "timeline_file": None,
        "entities": None,
        "timestamp": None,
        "counts": None,
        "selected_db": old_db,
        "prompt": None,
        "topicos": None,
        "resumo": None,
        "pessoas_organizacoes": None,
        "dados_mapa": None,
        "xml_final": None,
        "caminhos_imagens": None,
        "filtros_utilizados": None,
        "conteudos_tabelas": None
    }
    return jsonify({"status": "success"})

@app.route('/process_sentiment', methods=['POST'])
def process_sentiment():
    """
    Retorna o HTML fixo/dinâmico gerado, mas agora sem usar shared_content["text"].
    Faz nova análise com base no último conteúdo do DB, e retorna o HTML.
    """
    db_path = shared_content.get("selected_db")
    if not db_path or not os.path.isfile(db_path):
        return jsonify({"error": "Nenhum DB selecionado"}), 400

    last_entry = fetch_last_ingested_content(db_path)
    if not last_entry:
        return jsonify({"error": "Sem conteúdo no DB para analisar"}), 400
    analysis_text = last_entry["conteudo"]

    # Reexecuta a análise, gera o HTML e retorna
    try:
        html_fixed, html_dynamic, num_pars, num_sents, _ = sentiment_analyzer.execute_analysis_text(analysis_text)
        return jsonify({
            "html_fixed": {
                "analyzedText": html_fixed,
                "timestamp": time.strftime('%Y%m%d_%H%M%S'),
                "counts": f"Parágrafos: {num_pars}, Frases: {num_sents}",
            },
            "html_dynamic": html_dynamic
        })
    except Exception:
        return jsonify({"error": "HTML content not generated yet."}), 400

@app.route('/select_algorithm_and_generate', methods=['POST'])
def select_algorithm_and_generate():
    """
    Seleciona o algoritmo e gera novamente a análise de sentimentos, se necessário.
    Agora também busca o texto do DB em vez de shared_content["text"].
    """
    algorithm = request.form.get('algorithm', None)
    if not algorithm:
        return jsonify({"error": "Nenhum algoritmo selecionado"}), 400

    if algorithm != "naive_bayes":
        return jsonify({"error": "Algoritmo não suportado"}), 400

    db_path = shared_content.get("selected_db")
    if not db_path or not os.path.isfile(db_path):
        return jsonify({"error": "Nenhum DB selecionado"}), 400

    last_entry = fetch_last_ingested_content(db_path)
    if not last_entry:
        return jsonify({"error": "Não há texto no DB para análise"}), 400

    text = last_entry["conteudo"]
    if not text.strip():
        return jsonify({"error": "Nenhum texto fornecido para análise"}), 400

    try:
        # Gera novamente
        sentiment_analyzer.execute_analysis_text(text)
        return jsonify({"status": "Análise concluída"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/process', methods=['POST'])
def process():
    """
    Processa Representações Sociais, recuperando do DB.
    """
    db_path = shared_content.get("selected_db")
    if not db_path:
        return jsonify({"error": "Nenhum DB selecionado"}), 400

    last_entry = fetch_last_ingested_content(db_path)
    if not last_entry:
        return jsonify({"error": "Nenhum texto no DB"}), 400

    text_for_analysis = last_entry["conteudo"]
    if not text_for_analysis.strip():
        return jsonify({"error": "Texto no DB está vazio"}), 400

    # Agora chamamos a função de representações sociais
    response_data = process_representacao_social(
        text_for_analysis,
        request.form,
        app.config['UPLOAD_FOLDER']
    )
    if not isinstance(response_data, dict):
        return jsonify({"error": "process_representacao_social não retornou dicionário."}), 500

    # Armazena metadados para posterior salvamento
    filters_aplicados = (request.form.get('stopwords', '') + " | " +
                         request.form.get('zone', '') + " | " +
                         request.form.get('extra_filter', ''))
    shared_content["filtros_utilizados"] = filters_aplicados
    if "caminhos_imagens" in response_data:
        shared_content["caminhos_imagens"] = response_data["caminhos_imagens"]
    if "conteudos_tabelas" in response_data:
        shared_content["conteudos_tabelas"] = response_data["conteudos_tabelas"]

    return response_data

@app.route('/identify_entities', methods=['POST'])
def identify_entities():
    """
    Identifica entidades e localidades, salvando ou memoizando o resultado, 
    mas sem cache local de texto.
    """
    db_path = shared_content.get("selected_db")
    if not db_path or not os.path.isfile(db_path):
        return jsonify({"error": "Nenhum DB selecionado ou DB inexistente"}), 400

    last_entry = fetch_last_ingested_content(db_path)
    if not last_entry:
        return jsonify({"error": "Nenhum texto disponível no DB"}), 400

    analysis_text = last_entry["conteudo"]
    if not analysis_text.strip():
        return jsonify({"error": "Texto vazio no DB"}), 400

    try:
        existing_result = memoize_result(db_path, "entity_finder", analysis_text)
        if existing_result:
            import json
            try:
                parsed = json.loads(existing_result)
                shared_content["entities"] = parsed
                return jsonify({"status": "cached", "entities": parsed})
            except:
                shared_content["entities"] = existing_result
                return jsonify({"status": "cached", "entities": existing_result})

        # Se não existe, processamos
        result_obj = process_text(analysis_text, entity_classifier)  # dict ou similar
        shared_content["entities"] = result_obj
        store_memo_result(db_path, "entity_finder", analysis_text, str(result_obj))
        return jsonify({"status": "success", "entities": result_obj})
    except Exception as e:
        print(f"Erro durante a identificação de entidades: {e}")
        return jsonify({"error": "Erro ao identificar entidades"}), 500

@app.route('/generate_timeline', methods=['POST'])
def generate_timeline():
    """
    Gera timeline a partir do texto do DB ou do form.
    """
    text = request.form.get("text", "").strip()
    db_path = shared_content.get("selected_db")
    if not db_path:
        return jsonify({"error": "Nenhum DB selecionado"}), 400

    if not text:
        # Se veio vazio, tentamos o DB
        last_entry = fetch_last_ingested_content(db_path)
        if not last_entry or not last_entry["conteudo"].strip():
            return jsonify({"error": "Texto não fornecido nem disponível no DB"}), 400
        text = last_entry["conteudo"]

    existing_result = memoize_result(db_path, "timeline", text)
    if existing_result:
        shared_content["timeline_file"] = existing_result
        shared_content["xml_final"] = existing_result
        return jsonify({"status": "cached", "timeline_file": existing_result})

    try:
        timeline_file = TimelineGenerator().create_timeline(text.splitlines())
        shared_content["timeline_file"] = timeline_file
        shared_content["xml_final"] = timeline_file
        store_memo_result(db_path, "timeline", text, timeline_file)
        return jsonify({"status": "success", "timeline_file": timeline_file})
    except Exception as e:
        return jsonify({"error": f"Erro ao gerar timeline: {str(e)}"}), 500

@app.route('/view_timeline', methods=['GET'])
def view_timeline():
    filename = request.args.get('file')
    if not filename:
        return jsonify({"status": "error", "message": "Nome do arquivo não fornecido"}), 400

    timeline_file = os.path.join("static/generated/timeline_output", filename)
    if not os.path.isfile(timeline_file):
        return jsonify({"status": "error", "message": f"Arquivo não encontrado: {timeline_file}"}), 404

    html_str = render_template('timeline.html')
    return jsonify({"status": "success", "html": html_str, "filename": filename})

@app.route('/list_timelines')
def list_timelines():
    timeline_dir = "static/generated/timeline_output"
    try:
        timelines = [f for f in os.listdir(timeline_dir) if f.endswith('.timeline')]
        return jsonify({"status": "success", "timelines": timelines})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/timeline_data')
def timeline_data():
    filename = request.args.get('file')
    if not filename:
        return jsonify({"error": "Nome do arquivo não fornecido"}), 400

    timeline_file = os.path.join("static/generated/timeline_output", filename)
    if not os.path.isfile(timeline_file):
        return jsonify({"error": f"Arquivo não encontrado: {timeline_file}"}), 404

    parser = TimelineParser()
    try:
        data = parser.parse_timeline_xml(timeline_file)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Falha ao parsear {timeline_file}: {str(e)}"}), 500

@app.route('/generate_cenarios', methods=['POST'])
def generate_cenarios():
    """
    Agora, de fato chamamos o script 'prospect.py':
      - Raspamos/resgatamos texto do DB
      - Processamos com TextProcessor => geramos resumo/topicos
      - Chamamos EntityClassifier => geramos cenários via OpenAI
      - Retornamos o HTML
    """
    db_path = shared_content.get("selected_db")
    if not db_path:
        return jsonify({"error": "Nenhum DB selecionado"}), 400

    last_entry = fetch_last_ingested_content(db_path)
    if not last_entry or not last_entry["conteudo"].strip():
        return jsonify({"error": "Nenhum texto disponível para gerar cenários."}), 400

    combined_text = last_entry["conteudo"]
    
    # 1) Gerar resumo e tópicos
    tp = TextProcessor(combined_text)
    resumo, topicos = tp.process_text()

    # 2) Gerar cenários com EntityClassifier
    classifier = ScenarioClassifier(resumo, topicos, combined_text)
    prompt_final = classifier.generate_prompt()
    conteudo_openai = classifier.call_openai_api(prompt_final)
    
    # 3) Obter HTML resultante (cenários)
    html_resp, cenarios_dict = classifier.generate_html(conteudo_openai)
    
    return jsonify({"html": html_resp})

@app.route('/api/', methods=['POST'])
def receive_dom():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        dom_content = data.get("dom", "")
        page_url = data.get("url", "Unknown URL")

        if not dom_content:
            return jsonify({"error": "No DOM content provided"}), 400

        print(f"API: DOM from {page_url}, length={len(dom_content)}")
        return jsonify({"status": "success", "message": "DOM received"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/llama_query', methods=['POST'])
def llama_query():
    """
    Rota de exemplo para atender /llama_query e evitar erro 404.
    Aqui, retornamos uma resposta dummy ou integrariamos com LlamaIndex real.
    """
    data = request.get_json(force=True)
    question = data.get("question", "")
    if not question.strip():
        return jsonify({"error": "Pergunta vazia"}), 400
    # Exemplo: resposta dummy
    resposta = f"Resposta simulada para: {question}"
    return jsonify({"answer": resposta})

if __name__ == "__main__":
    print(">>> Iniciando aplicação Flask em modo debug.")
    import os
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        ts = time.strftime('%Y%m%d_%H%M%S')
        default_db_path = os.path.join(DB_FOLDER, f"{ts}.db")
        if not os.path.isfile(default_db_path):
            create_db_if_not_exists(default_db_path)
            print(f"DB '{ts}.db' criado em: {default_db_path}")

    app.run(debug=True)
