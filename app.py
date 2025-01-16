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

# Conteúdo compartilhado global (mantém o texto atual, resultados etc.)
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
            texto_analisado=shared_content.get("text", ""),
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
            texto_analisado=shared_content.get("text", ""),
            xml_final=shared_content.get("xml_final", "")
        )

    # Se existir análise de sentimentos
    if shared_content.get("html_dynamic"):
        save_sentimentos(
            db_path=db_path,
            texto_analisado=shared_content.get("text", ""),
            caminhos_imagens="(imagens geradas em pasta static, se houver)"
        )

    # Se existir representação social
    if shared_content.get("filtros_utilizados") or shared_content.get("conteudos_tabelas"):
        save_representacao_social(
            db_path=db_path,
            texto_analisado=shared_content.get("text", ""),
            filtros_utilizados=shared_content.get("filtros_utilizados", ""),
            caminhos_imagens=shared_content.get("caminhos_imagens", ""),
            conteudos_tabelas=shared_content.get("conteudos_tabelas", "")
        )

    # Se existir cenários
    if shared_content.get("topicos") or shared_content.get("resumo"):
        save_contexto(
            db_path=db_path,
            texto_analisado=shared_content.get("text", ""),
            prompt=shared_content.get("prompt", ""),
            topicos=shared_content.get("topicos", ""),
            resumo=shared_content.get("resumo", ""),
            conteudos_tabelas=shared_content.get("conteudos_tabelas", "")
        )

    return jsonify({"status": "success", "message": "Dados salvos no DB com sucesso."})

@app.route('/ingest_content', methods=['POST'])
def ingest_content():
    """
    Ingestão de texto via arquivo .txt ou texto copiado,
    e subsequente análise de sentimentos.
    """
    global shared_content

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
        # Lê o conteúdo do arquivo diretamente
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
        fonte_usada = "links"
        # Em tese, preferimos a rota /ingest_links
        return jsonify({"error": "Use /ingest_links para enviar links."}), 400

    if not final_text.strip():
        return jsonify({"error": "Nenhum conteúdo fornecido"}), 400

    # Usamos a timestamp do DB para exibir data se quisermos,
    # mas aqui continuamos gerando uma local (exibição interna):
    shared_content["text"] = final_text
    shared_content["algorithm"] = "naive_bayes"
    shared_content["timestamp"] = time.strftime('%Y%m%d_%H%M%S')

    # Executa análise de sentimentos
    try:
        html_fixed, html_dynamic, num_pars, num_sents, _ = sentiment_analyzer.execute_analysis_text(final_text)
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
    Ingestão de texto por links, com raspagem e subsequente análise de sentimentos.
    """
    global shared_content
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
        shared_content["text"] = combined_text
        shared_content["bad_links"] = bad_links
    except Exception as e:
        print(f"Erro durante raspagem de links: {e}")
        return jsonify({"error": f"Erro ao raspar links: {str(e)}"}), 500

    # Registrar cada link e seu conteúdo
    for link in links_list:
        insert_link_raspado(db_path, link, shared_content["text"])

    shared_content["algorithm"] = "naive_bayes"
    shared_content["timestamp"] = time.strftime('%Y%m%d_%H%M%S')

    # Executa análise de sentimentos
    try:
        html_fixed, html_dynamic, num_pars, num_sents, _ = sentiment_analyzer.execute_analysis_text(
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
                "timestamp": shared_content["timestamp"],
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
    # Preserve apenas o selected_db; zere o restante
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
    Retorna o HTML fixo/dinâmico já gerado pela análise de sentimentos.
    """
    if not shared_content.get("text"):
        return jsonify({"error": "No content provided"}), 400
    if not shared_content.get("algorithm"):
        return jsonify({"error": "No algorithm selected"}), 400

    if not shared_content.get("html_fixed") or not shared_content.get("html_dynamic"):
        return jsonify({"error": "HTML content not generated yet."}), 400

    return jsonify({
        "html_fixed": {
            "analyzedText": shared_content["html_fixed"],
            "timestamp": shared_content.get("timestamp", ""),
            "counts": shared_content.get("counts", ""),
        },
        "html_dynamic": shared_content["html_dynamic"]
    })

@app.route('/select_algorithm_and_generate', methods=['POST'])
def select_algorithm_and_generate():
    """
    Seleciona o algoritmo e gera novamente a análise de sentimentos, se necessário.
    """
    algorithm = request.form.get('algorithm', None)
    if not algorithm:
        return jsonify({"error": "Nenhum algoritmo selecionado"}), 400

    if algorithm != "naive_bayes":
        return jsonify({"error": "Algoritmo não suportado"}), 400

    shared_content["algorithm"] = algorithm
    text = shared_content.get("text", "")
    if not text.strip():
        return jsonify({"error": "Nenhum texto fornecido para análise"}), 400

    try:
        html_fixed, html_dynamic, num_pars, num_sents, analysis_ts = sentiment_analyzer.execute_analysis_text(text)
        shared_content["html_fixed"] = html_fixed
        shared_content["html_dynamic"] = html_dynamic
        # Não sobrescrever a timestamp do DB, mas podemos atualizar localmente
        shared_content["timestamp"] = analysis_ts
        shared_content["counts"] = f"Parágrafos: {num_pars}, Frases: {num_sents}"
        return jsonify({"status": "Análise concluída"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/process', methods=['POST'])
def process():
    """
    Processa Representações Sociais. Retorna um dicionário com 'html', 'caminhos_imagens', etc.
    e atualiza shared_content para posterior salvamento no DB.
    """
    if not shared_content["text"]:
        return jsonify({"error": "No content provided"}), 400

    # Corrigir: 'process_representacao_social' deve retornar um dicionário, não um Response.
    response_data = process_representacao_social(
        shared_content["text"],
        request.form,
        app.config['UPLOAD_FOLDER']
    )
    # Supondo que 'process_representacao_social' agora retorne algo como:
    # {
    #   "html": "...",
    #   "caminhos_imagens": "...",
    #   "conteudos_tabelas": "..."
    # }
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
    Identifica entidades e localidades, salvando ou memoizando o resultado.
    """
    text = shared_content.get("text", "")
    if not text.strip():
        return jsonify({"error": "Nenhum texto fornecido para análise"}), 400

    db_path = shared_content.get("selected_db")
    if not db_path or not os.path.isfile(db_path):
        return jsonify({"error": "Nenhum DB selecionado ou DB inexistente"}), 400

    try:
        existing_result = memoize_result(db_path, "entity_finder", text)
        if existing_result:
            # Se já existe, parseamos
            import json
            try:
                parsed = json.loads(existing_result)
                shared_content["entities"] = parsed
                return jsonify({"status": "cached", "entities": parsed})
            except:
                # Se não parsear, retorna a string
                shared_content["entities"] = existing_result
                return jsonify({"status": "cached", "entities": existing_result})

        # Se não existe, processamos
        result_obj = process_text(text, entity_classifier)  # dict ou similar
        shared_content["entities"] = result_obj
        # Armazena no DB
        store_memo_result(db_path, "entity_finder", text, str(result_obj))
        return jsonify({"status": "success", "entities": result_obj})
    except Exception as e:
        print(f"Erro durante a identificação de entidades: {e}")
        return jsonify({"error": "Erro ao identificar entidades"}), 500

@app.route('/generate_timeline', methods=['POST'])
def generate_timeline():
    """
    Gera timeline a partir do texto atual ou do form.
    """
    text = request.form.get("text", "")
    if not text.strip():
        # Se veio vazio no form, usa o que está no shared_content
        text = shared_content.get("text", "")
    if not text.strip():
        return jsonify({"error": "Texto não fornecido"}), 400

    db_path = shared_content.get("selected_db")
    if not db_path:
        return jsonify({"error": "Nenhum DB selecionado"}), 400

    # Verifica se já existe timeline memoizada para este texto
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

    # Renderizamos timeline.html e retornamos em JSON
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

# Nova rota para gerar cenários (aba "Cenários")
@app.route('/generate_cenarios', methods=['POST'])
def generate_cenarios():
    """
    Exemplo mínimo de geração de cenários, que poderia chamar um outro módulo.
    Aqui, apenas setamos 'topicos', 'resumo' e 'conteudos_tabelas' no shared_content.
    """
    text = shared_content.get("text", "")
    if not text.strip():
        return jsonify({"error": "Nenhum texto disponível para gerar cenários."}), 400

    # Exemplo: geramos algo simples
    shared_content["topicos"] = "Cenário A, Cenário B, Cenário C"
    shared_content["resumo"] = "Sumário sintético..."
    shared_content["conteudos_tabelas"] = "Tabela de suporte..."

    # Montamos HTML de exemplo
    html_resp = f"""
    <h3>Cenários Possíveis</h3>
    <ul>
      <li>{shared_content["topicos"]}</li>
    </ul>
    <p>{shared_content["resumo"]}</p>
    """

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

# Criação do DB ao iniciar a aplicação (para evitar duplicidade no modo debug, usamos 'WERKZEUG_RUN_MAIN')
if __name__ == "__main__":
    print(">>> Iniciando aplicação Flask em modo debug.")
    import os
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Só no reload "real" do Flask
        ts = time.strftime('%Y%m%d_%H%M%S')
        default_db_path = os.path.join(DB_FOLDER, f"{ts}.db")
        if not os.path.isfile(default_db_path):
            create_db_if_not_exists(default_db_path)
            print(f"DB '{ts}.db' criado em: {default_db_path}")

    app.run(debug=True)
