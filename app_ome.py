from flask import Flask, request, render_template, jsonify
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Usar backend non-interactive para evitar problemas com threads
import matplotlib.pyplot as plt
import os
import re
import nltk
import time
from nltk.corpus import stopwords
from sent_bayes import SentimentAnalyzer

# Baixar dependências do NLTK
nltk.download('punkt')
nltk.download('stopwords')

app = Flask(__name__)
UPLOAD_FOLDER = './static/generated'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Garantir que o diretório de saída exista
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Variável global para armazenar conteúdo compartilhado
shared_content = {"text": None, "html_fixed": None, "html_dynamic": None, "algorithm": None}

class RepresentacaoSocial:
    def __init__(self, textos):
        self.textos = [self._limpar_pontuacao(texto) for texto in textos]
        self.data = self._preparar_dados()

    def _limpar_pontuacao(self, texto):
        return re.sub(r'[^\w\s]', '', texto)

    def _preparar_dados(self):
        palavras = []
        ordem = []
        for i, texto in enumerate(self.textos):
            for j, palavra in enumerate(texto.split(), start=1):
                palavras.append(palavra.lower())
                ordem.append(j)
        return pd.DataFrame({'palavra': palavras, 'ordem': ordem})

    def calcular_frequencia_ome(self):
        frequencia = self.data['palavra'].value_counts().reset_index()
        frequencia.columns = ['palavra', 'frequencia']
        ome = self.data.groupby('palavra')['ordem'].mean().reset_index()
        ome.columns = ['palavra', 'OME']
        resultado = pd.merge(frequencia, ome, on='palavra')
        freq_quartil = resultado['frequencia'].median()
        ome_quartil = resultado['OME'].median()
        resultado['zona'] = resultado.apply(
            lambda row: (
                "Núcleo Central" if row['frequencia'] > freq_quartil and row['OME'] <= ome_quartil else
                "Zona Periférica 1" if row['frequencia'] <= freq_quartil and row['OME'] <= ome_quartil else
                "Zona Periférica 2" if row['frequencia'] > freq_quartil and row['OME'] > ome_quartil else
                "Zona Periférica 3"
            ),
            axis=1
        )
        self.resultado = resultado
        return resultado

    def gerar_grafico(self, df, filtro, zona):
        """Gera um gráfico baseado nos dados filtrados."""
        plt.figure(figsize=(6, 4))
        plt.scatter(df['frequencia'], df['OME'])
        plt.title(f"Gráfico para {filtro.capitalize()} Stopwords e {zona}")
        plt.xlabel('Frequência')
        plt.ylabel('OME')
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"grafico_{time.time()}.png")
        plt.savefig(filepath)
        plt.close()
        return filepath

# Inicializar SentimentAnalyzer
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
        shared_content["text"] = request.form['text']

    # Gerar conteúdo processado
    try:
        html_fixed, html_dynamic = sentiment_analyzer.execute_analysis_text(shared_content["text"])
        shared_content["html_fixed"] = html_fixed
        shared_content["html_dynamic"] = html_dynamic
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Erro durante a ingestão de conteúdo: {e}")
        return jsonify({"error": "Erro ao processar o conteúdo"}), 500

@app.route('/reset_content', methods=['POST'])
def reset_content():
    global shared_content
    shared_content = {"text": None, "html_fixed": None, "html_dynamic": None, "algorithm": None}
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
        html_fixed, html_dynamic = sentiment_analyzer.execute_analysis_text(text)
        shared_content["html_fixed"] = html_fixed
        shared_content["html_dynamic"] = html_dynamic
        return jsonify({"status": "Análise concluída"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/process', methods=['POST'])
def process():
    global shared_content
    if not shared_content["text"]:
        return jsonify({"error": "No content provided"}), 400

    textos = nltk.sent_tokenize(shared_content["text"])
    analise = RepresentacaoSocial(textos)
    resultado = analise.calcular_frequencia_ome()

    stopwords_filter = request.form.get('stopwords', 'com')
    zone_filter = request.form.get('zone', 'todas')
    stopwords_list = set(stopwords.words('portuguese'))

    if stopwords_filter == "com":
        palavras = resultado
    elif stopwords_filter == "sem":
        palavras = resultado[~resultado['palavra'].isin(stopwords_list)]
    elif stopwords_filter == "stopwords":
        palavras = resultado[resultado['palavra'].isin(stopwords_list)]
    else:
        palavras = resultado  # Valor padrão

    zonas = ["Núcleo Central", "Zona Periférica 1", "Zona Periférica 2", "Zona Periférica 3"]
    graficos_tabelas = []

    if zone_filter == "todas":
        for zona in zonas:
            zona_dados = palavras[palavras['zona'] == zona]
            grafico_path = analise.gerar_grafico(zona_dados, stopwords_filter, zona)
            graficos_tabelas.append({
                "zona": zona,
                "tabela": zona_dados.to_html(classes='table table-striped', index=False),
                "grafico": grafico_path
            })
    else:
        zona_dados = palavras[palavras['zona'] == zone_filter]
        grafico_path = analise.gerar_grafico(zona_dados, stopwords_filter, zone_filter)
        graficos_tabelas.append({
            "zona": zone_filter,
            "tabela": zona_dados.to_html(classes='table table-striped', index=False),
            "grafico": grafico_path
        })

    html = ""
    for item in graficos_tabelas:
        html += f"""
        <div class="zona-section">
            <h4>{item['zona']}</h4>
            <img src="{item['grafico']}" style="width: 100%; margin-bottom: 10px;" class="img-fluid">
            <div>{item['tabela']}</div>
        </div>
        <hr>
        """
    return jsonify({"html": html})

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

if __name__ == '__main__':
    app.run(debug=True)
