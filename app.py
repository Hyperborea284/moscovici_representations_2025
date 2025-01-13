from flask import Flask, request, render_template, jsonify
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import time
import sys

from modules.sent_bayes import SentimentAnalyzer
from modules.representacao_social import process_representacao_social
from modules.goose_scraper import scrape_links
from modules.timeline_generator import TimelineGenerator, TimelineParser

app = Flask(__name__)

# Configuração da pasta de upload
UPLOAD_FOLDER = './static/generated'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Garantir que o diretório de saída exista
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Variável global para armazenar conteúdo compartilhado
shared_content = {
    "text": None, 
    "html_fixed": None, 
    "html_dynamic": None, 
    "algorithm": None,
    # Lista de links que falharam
    "bad_links": [],
    "timeline_file": None
}

# Inicializar SentimentAnalyzer usando a mesma pasta de upload do app
sentiment_analyzer = SentimentAnalyzer(output_dir=UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html', shared_content=shared_content)

@app.route('/ingest_content', methods=['POST'])
def ingest_content():
    global shared_content
    uploaded_file = request.files.get('file')
    if uploaded_file and uploaded_file.filename:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
        uploaded_file.save(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            shared_content["text"] = f.read()
    else:
        # Use 'get' com valor padrão vazio para evitar KeyError
        shared_content["text"] = request.form.get('text', '')
    
    # >>>>>>> Atribuição para evitar erro 400 em /process_sentiment <<<<<<<
    shared_content["algorithm"] = "naive_bayes"
    shared_content["bad_links"] = []  # Zerar a lista de links ruins caso venha de arquivo/texto

    # Gerar conteúdo processado
    try:
        # Ajuste para receber 5 retornos (html_fixed, html_dynamic, num_pars, num_sents, timestamp)
        html_fixed, html_dynamic, num_pars, num_sents, analysis_ts = sentiment_analyzer.execute_analysis_text(
            shared_content["text"]
        )
        shared_content["html_fixed"] = html_fixed
        shared_content["html_dynamic"] = html_dynamic
        shared_content["timestamp"] = analysis_ts
        shared_content["counts"] = f"Parágrafos: {num_pars}, Frases: {num_sents}"

        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Erro durante a ingestão de conteúdo: {e}")
        return jsonify({"error": "Erro ao processar o conteúdo"}), 500

# >>>>>>> NOVA ROTA PARA INGESTÃO DE TEXTO A PARTIR DE LINKS <<<<<<<
@app.route('/ingest_links', methods=['POST'])
def ingest_links():
    global shared_content
    links_text = request.form.get('links', '')
    if not links_text.strip():
        return jsonify({"error": "Nenhum link fornecido"}), 400

    # Separar links por linha ou outro delimitador desejado
    links_list = [l.strip() for l in links_text.splitlines() if l.strip()]
    if not links_list:
        return jsonify({"error": "Nenhum link válido fornecido"}), 400

    # Raspagem de conteúdo usando o módulo goose_scraper
    try:
        combined_text, bad_links = scrape_links(links_list)
        shared_content["text"] = combined_text
        shared_content["bad_links"] = bad_links
    except Exception as e:
        print(f"Erro durante raspagem de links: {e}")
        return jsonify({"error": f"Erro ao raspar links: {str(e)}"}), 500

    # Ajuste para evitar erro 400 em /process_sentiment
    shared_content["algorithm"] = "naive_bayes"

    # Gerar conteúdo processado tal como é feito nas outras ingestões
    try:
        html_fixed, html_dynamic, num_pars, num_sents, analysis_ts = sentiment_analyzer.execute_analysis_text(
            shared_content["text"]
        )
        shared_content["html_fixed"] = html_fixed
        shared_content["html_dynamic"] = html_dynamic
        shared_content["timestamp"] = analysis_ts
        shared_content["counts"] = f"Parágrafos: {num_pars}, Frases: {num_sents}"

        # Retornamos também a lista de bad_links e os campos processados para o front-end
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
        "timeline_file": None
    }
    return jsonify({"status": "success"})

@app.route('/select_algorithm_and_generate', methods=['POST'])
def select_algorithm_and_generate():
    """Seleciona o algoritmo e realiza a análise de sentimentos."""
    global shared_content
    algorithm = request.form.get('algorithm', None)
    if not algorithm:
        return jsonify({"error": "Nenhum algoritmo selecionado"}), 400

    # Atualizar para permitir apenas o algoritmo Naive Bayes
    if algorithm != "naive_bayes":
        return jsonify({"error": "Algoritmo não suportado"}), 400

    shared_content["algorithm"] = algorithm

    # Validação do texto
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

@app.route('/process', methods=['POST'])
def process():
    """
    Rota para análise de Representação Social. 
    A funcionalidade foi movida para a função process_representacao_social,
    importada do script representacao_social.py.
    """
    global shared_content
    if not shared_content["text"]:
        return jsonify({"error": "No content provided"}), 400

    # Chama a função que faz todo o cálculo e retorna o HTML
    return process_representacao_social(
        shared_content["text"],
        request.form,
        app.config['UPLOAD_FOLDER']
    )

@app.route('/process_sentiment', methods=['POST'])
def process_sentiment():
    """Processa a análise de sentimentos e retorna o conteúdo dinâmico gerado."""
    global shared_content
    if not shared_content.get("text"):
        return jsonify({"error": "No content provided"}), 400
    if not shared_content.get("algorithm"):
        return jsonify({"error": "No algorithm selected"}), 400

    try:
        # Verifica se os conteúdos fixo e dinâmico estão disponíveis
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

# >>>>>>> NOVA ROTA PARA GERAÇÃO DE TIMELINE <<<<<<<
@app.route('/generate_timeline', methods=['POST'])
def generate_timeline():
    """
    Rota para gerar a timeline a partir do conteúdo de texto já ingerido,
    sem qualquer referência ao Goose no script de timeline.
    """
    global shared_content

    # Pega o que vier do front-end
    text = request.form.get("text", "")
    
    # Se vier vazio, tenta usar o que já está armazenado em shared_content
    if not text:
        text = shared_content.get("text", "")
    
    if not text.strip():
        return jsonify({"error": "Texto não fornecido"}), 400

    try:
        timeline_file = TimelineGenerator().create_timeline(text.splitlines())
        shared_content["timeline_file"] = timeline_file
        return jsonify({"status": "success", "timeline_file": timeline_file})
    except Exception as e:
        return jsonify({"error": f"Erro ao gerar timeline: {str(e)}"}), 500

# >>>>>>> ROTA PARA VISUALIZAÇÃO DE TIMELINE (ALTERADA) <<<<<<<
@app.route('/view_timeline', methods=['GET'])
def view_timeline():
    """
    Rota para exibir a timeline gerada, agora retornando 'timeline.html' via JSON.
    """
    global shared_content
    timeline_file = shared_content.get("timeline_file")
    if not timeline_file:
        return jsonify({"error": "Nenhuma timeline gerada"}), 400

    # Verificar se o arquivo .timeline existe fisicamente
    if not os.path.isfile(timeline_file):
        return jsonify({"error": f"Arquivo não encontrado: {timeline_file}"}), 404

    # Renderiza o template timeline.html
    html_str = render_template('timeline.html')

    # Devolve o HTML dentro de um objeto JSON
    return jsonify({"status": "success", "html": html_str})

@app.route('/timeline_data')
def timeline_data():
    """
    Rota que parseia o arquivo .timeline armazenado em shared_content
    e retorna os dados em JSON para o D3 desenhar.
    """
    global shared_content
    timeline_file = shared_content.get("timeline_file")
    if not timeline_file:
        return jsonify({"error": "Nenhuma timeline gerada"}), 400

    parser = TimelineParser()
    try:
        data = parser.parse_timeline_xml(timeline_file)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Falha ao parsear {timeline_file}: {str(e)}"}), 500

# Rota para receber o DOM (Parece ser usada para debug; se não for necessária, pode ser removida)
@app.route('/api/', methods=['POST'])  # Altere 'api' para 'app' se necessário
def receive_dom():
    try:
        print("API: Received a POST request")
        # Recebe o conteúdo enviado em formato JSON
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

        # Apresenta o URL e o DOM recebido
        print(f"API: Received DOM from URL: {page_url}")
        print("API: Received DOM length:", len(dom_content))
        print("API: First 500 characters of DOM:")
        print(dom_content[:500])

        # Retorna confirmação
        return jsonify({"status": "success", "message": "DOM received"}), 200
    except Exception as e:
        print("API: Exception occurred:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
