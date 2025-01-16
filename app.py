from flask import Flask, request, render_template, jsonify
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import time
import sys
from dotenv import load_dotenv

from modules.sent_bayes import SentimentAnalyzer
from modules.representacao_social import process_representacao_social
from modules.goose_scraper import scrape_links
from modules.timeline_generator import TimelineGenerator, TimelineParser
from modules.entity_finder import EntityClassifier, process_text  # Importar funções de entity_finder

# >>> IMPORTAMOS NOSSO GESTOR DE DB <<<
from modules.db_manager import (
    get_db_path,
    create_db_if_not_exists,
    insert_content_ingestao,
    insert_link_raspado,
    memoize_result,
    store_memo_result,
    list_existing_dbs
)

# Carregar variáveis de ambiente
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("A chave da API não foi encontrada. Verifique o arquivo .env.")

serp_api_key = os.getenv("SERP_API_KEY")
if not serp_api_key:
    raise ValueError("A chave da API não foi encontrada. Verifique o arquivo .env.")

# Inicializar o Flask
app = Flask(__name__)

# Configuração da pasta de upload
UPLOAD_FOLDER = './static/generated'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Definimos a pasta onde os DBs ficarão
DB_FOLDER = './dbs'
os.makedirs(DB_FOLDER, exist_ok=True)

# Inicializar o EntityClassifier com a chave da OpenAI
entity_classifier = EntityClassifier(openai_api_key, serp_api_key)

# Variável global para armazenar conteúdo compartilhado
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
    # Podemos expandir para armazenar o db selecionado caso seja necessário
    "selected_db": None
}

# Inicializar SentimentAnalyzer
sentiment_analyzer = SentimentAnalyzer(output_dir=UPLOAD_FOLDER)

@app.route('/')
def index():
    """
    Renderiza a página principal.
    Deve conter as abas:
      1) Selecionar DB
      2) Texto via arquivo
      3) Texto de links
      4) Texto via extensão
      (E as subsequentes de análise: Entidades, Timeline, Sentimentos, Representações Sociais)
    """
    return render_template('index.html', shared_content=shared_content)

# >>>>>>> NOVA ROTA: SELECIONAR DB <<<<<<<
@app.route('/select_db', methods=['GET', 'POST'])
def select_db():
    """
    Exibe a lista de DBs disponíveis no DB_FOLDER e permite a seleção de um DB para uso.
    """
    db_files = list_existing_dbs(DB_FOLDER)

    if request.method == 'POST':
        selected_db = request.form.get('db_name', '')
        if selected_db and selected_db in db_files:
            shared_content["selected_db"] = os.path.join(DB_FOLDER, selected_db)
            return jsonify({"status": "success", "selected_db": selected_db})
        else:
            return jsonify({"error": "DB inválido ou inexistente"}), 400

    return render_template('select_db.html', db_files=db_files)

# >>>>>>> ROTAS DA INGESTÃO DE CONTEÚDOS <<<<<<<
@app.route('/ingest_content', methods=['POST'])
def ingest_content():
    global shared_content
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

    # Geramos um timestamp para este "envio de conteúdo"
    analysis_ts = time.strftime('%Y%m%d_%H%M%S')
    db_path = get_db_path(DB_FOLDER, analysis_ts)
    create_db_if_not_exists(db_path)

    final_text = ""
    fonte_usada = ""

    if uploaded_file and uploaded_file.filename:
        fonte_usada = "arquivo"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
        uploaded_file.save(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            final_text = f.read()

    elif text_input:
        fonte_usada = "texto_copiado"
        final_text = text_input

    elif links_input:
        fonte_usada = "links"
        links_list = [l.strip() for l in links_input.splitlines() if l.strip()]
        if links_list:
            try:
                combined_text, bad_links = scrape_links(links_list)
                final_text = combined_text
                shared_content["bad_links"] = bad_links
            except Exception as e:
                return jsonify({"error": f"Erro ao raspar links: {str(e)}"}), 500

    # Guardamos no shared_content
    shared_content["text"] = final_text
    shared_content["algorithm"] = "naive_bayes"
    shared_content["bad_links"] = shared_content.get("bad_links", [])
    shared_content["timestamp"] = analysis_ts

    # Registramos no DB
    if fonte_usada == "links":
        for lnk in links_input.splitlines():
            lnk = lnk.strip()
            if lnk:
                insert_link_raspado(db_path, lnk, final_text)
    else:
        insert_content_ingestao(db_path, fonte_usada, final_text)

    try:
        html_fixed, html_dynamic, num_pars, num_sents, analysis_ts_2 = sentiment_analyzer.execute_analysis_text(
            shared_content["text"]
        )

        shared_content["html_fixed"] = html_fixed
        shared_content["html_dynamic"] = html_dynamic
        shared_content["counts"] = f"Parágrafos: {num_pars}, Frases: {num_sents}"

        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Erro durante a ingestão de conteúdo: {e}")
        return jsonify({"error": "Erro ao processar o conteúdo"}), 500

@app.route('/ingest_links', methods=['POST'])
def ingest_links():
    """
    Rota separada para ingestão de links, gera um DB com base no timestamp.
    """
    global shared_content
    links_text = request.form.get('links', '')
    if not links_text.strip():
        return jsonify({"error": "Nenhum link fornecido"}), 400

    links_list = [l.strip() for l in links_text.splitlines() if l.strip()]
    if not links_list:
        return jsonify({"error": "Nenhum link válido fornecido"}), 400

    analysis_ts = time.strftime('%Y%m%d_%H%M%S')
    db_path = get_db_path(DB_FOLDER, analysis_ts)
    create_db_if_not_exists(db_path)

    try:
        combined_text, bad_links = scrape_links(links_list)
        shared_content["text"] = combined_text
        shared_content["bad_links"] = bad_links
    except Exception as e:
        print(f"Erro durante raspagem de links: {e}")
        return jsonify({"error": f"Erro ao raspar links: {str(e)}"}), 500

    for link in links_list:
        insert_link_raspado(db_path, link, shared_content["text"])

    shared_content["algorithm"] = "naive_bayes"
    shared_content["timestamp"] = analysis_ts

    try:
        html_fixed, html_dynamic, num_pars, num_sents, analysis_ts_2 = sentiment_analyzer.execute_analysis_text(
            shared_content["text"]
        )
        shared_content["html_fixed"] = html_fixed
        shared_content["html_dynamic"] = html_dynamic
        shared_content["counts"] = f"Parágrafos: {num_pars}, Frases: {num_sents}"

        return jsonify({
            "status": "success",
            "bad_links": bad_links,
            "html_fixed": {
                "analyzedText": html_fixed,
                "timestamp": analysis_ts,
                "counts": f"Parágrafos: {num_pars}, Frases: {num_sents}",
            },
            "html_dynamic": html_dynamic
        })
    except Exception as e:
        print(f"Erro durante a ingestão de conteúdo via links: {e}")
        return jsonify({"error": "Erro ao processar o conteúdo"}), 500

@app.route('/reset_content', methods=['POST'])
def reset_content():
    global shared_content
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
        "selected_db": None
    }
    return jsonify({"status": "success"})

# >>>>>>> ROTAS DA ANÁLISE DE SENTIMENTOS <<<<<<<
@app.route('/process_sentiment', methods=['POST'])
def process_sentiment():
    global shared_content
    if not shared_content.get("text"):
        return jsonify({"error": "No content provided"}), 400
    if not shared_content.get("algorithm"):
        return jsonify({"error": "No algorithm selected"}), 400

    try:
        if not shared_content.get("html_fixed") or not shared_content.get("html_dynamic"):
            raise ValueError("HTML content not generated yet.")

        return jsonify({
            "html_fixed": {
                "analyzedText": shared_content["html_fixed"],
                "timestamp": shared_content.get("timestamp", ""),
                "counts": shared_content.get("counts", ""),
            },
            "html_dynamic": shared_content["html_dynamic"]
        })
    except Exception as e:
        app.logger.error(f"Error processing sentiment analysis: {e}")
        return jsonify({"error": f"Processing error: {e}"}), 500

@app.route('/select_algorithm_and_generate', methods=['POST'])
def select_algorithm_and_generate():
    global shared_content
    algorithm = request.form.get('algorithm', None)
    if not algorithm:
        return jsonify({"error": "Nenhum algoritmo selecionado"}), 400

    if algorithm != "naive_bayes":
        return jsonify({"error": "Algoritmo não suportado"}), 400

    shared_content["algorithm"] = algorithm
    text = shared_content.get("text")
    if not text:
        return jsonify({"error": "Nenhum texto fornecido para análise"}), 400

    try:
        html_fixed, html_dynamic, num_pars, num_sents, analysis_ts = sentiment_analyzer.execute_analysis_text(text)
        shared_content["html_fixed"] = html_fixed
        shared_content["html_dynamic"] = html_dynamic
        shared_content["timestamp"] = analysis_ts
        shared_content["counts"] = f"Parágrafos: {num_pars}, Frases: {num_sents}"

        return jsonify({"status": "Análise concluída"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

# >>>>>>> ROTAS DAS REPRESENTAÇÕES SOCIAIS <<<<<<<
@app.route('/process', methods=['POST'])
def process():
    global shared_content
    if not shared_content["text"]:
        return jsonify({"error": "No content provided"}), 400

    return process_representacao_social(
        shared_content["text"],
        request.form,
        app.config['UPLOAD_FOLDER']
    )

# >>>>>>> ROTAS DAS ENTIDADES E MAPA <<<<<<<
@app.route('/identify_entities', methods=['POST'])
def identify_entities():
    global shared_content
    if not shared_content.get("text"):
        return jsonify({"error": "Nenhum texto fornecido para análise"}), 400

    try:
        db_path = get_db_path(DB_FOLDER, shared_content.get("timestamp", ""))
        existing_result = memoize_result(db_path, "entity_finder", shared_content["text"])
        if existing_result:
            shared_content["entities"] = existing_result
            return jsonify({"status": "cached", "entities": existing_result})

        result_obj = process_text(shared_content["text"], entity_classifier)
        shared_content["entities"] = result_obj
        store_memo_result(db_path, "entity_finder", shared_content["text"], str(result_obj))

        return jsonify({"status": "success", "entities": result_obj})
    except Exception as e:
        print(f"Erro durante a identificação de entidades: {e}")
        return jsonify({"error": "Erro ao identificar entidades"}), 500

# >>>>>>> ROTAS DA TIMELINE <<<<<<<
@app.route('/generate_timeline', methods=['POST'])
def generate_timeline():
    global shared_content
    text = request.form.get("text", "")
    if not text:
        text = shared_content.get("text", "")
    if not text.strip():
        return jsonify({"error": "Texto não fornecido"}), 400

    try:
        db_path = get_db_path(DB_FOLDER, shared_content.get("timestamp", ""))
        existing_result = memoize_result(db_path, "timeline", text)
        if existing_result:
            shared_content["timeline_file"] = existing_result
            return jsonify({"status": "cached", "timeline_file": existing_result})

        timeline_file = TimelineGenerator().create_timeline(text.splitlines())
        shared_content["timeline_file"] = timeline_file
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

# >>>>>>> ROTA DO DOM <<<<<<<
@app.route('/api/', methods=['POST'])
def receive_dom():
    try:
        print("API: Received a POST request")
        data = request.get_json()
        print("API: JSON payload:", data)

        if not data:
            print("API: No JSON data received")
            return jsonify({"error": "No JSON data received"}), 400

        dom_content = data.get("dom", "")
        page_url = data.get("url", "Unknown URL")

        if not dom_content:
            print("API: No DOM content provided")
            return jsonify({"error": "No DOM content provided"}), 400

        print(f"API: Received DOM from URL: {page_url}")
        print("API: Received DOM length:", len(dom_content))
        print("API: First 500 characters of DOM:")
        print(dom_content[:500])

        return jsonify({"status": "success", "message": "DOM received"}), 200
    except Exception as e:
        print("API: Exception occurred:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print(">>> Iniciando aplicação Flask em modo debug.")
    app.run(debug=True)
