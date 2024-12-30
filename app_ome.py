from flask import Flask, request, render_template, jsonify
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Usar backend non-interactive
import matplotlib.pyplot as plt
import os
import re
import nltk
import time
from nltk.corpus import stopwords

# Baixar dependências do NLTK
nltk.download('punkt')
nltk.download('stopwords')

app = Flask(__name__)
UPLOAD_FOLDER = './static/generated'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Garantir que o diretório de saída exista
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
        plt.figure(figsize=(6, 4))
        plt.scatter(df['frequencia'], df['OME'])
        plt.title(f"Gráfico para {filtro.capitalize()} Stopwords e {zona}")
        plt.xlabel('Frequência')
        plt.ylabel('OME')
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"grafico_{time.time()}.png")
        plt.savefig(filepath)
        plt.close()
        return filepath

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    # Limpar diretório de gráficos antigos antes de processar a nova solicitação
    for file in os.listdir(app.config['UPLOAD_FOLDER']):
        if file.endswith('.png'):
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file))

    # Processar entrada de texto ou arquivo
    uploaded_file = request.files.get('file')
    if uploaded_file and uploaded_file.filename:
        uploaded_file_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
        uploaded_file.save(uploaded_file_path)
        with open(uploaded_file_path, 'r', encoding='utf-8') as f:
            uploaded_text = f.read()
    else:
        uploaded_text = request.form['text']

    textos = nltk.sent_tokenize(uploaded_text)
    analise = RepresentacaoSocial(textos)
    resultado = analise.calcular_frequencia_ome()

    # Filtragem com base nas opções selecionadas
    stopwords_filter = request.form['stopwords']
    zone_filter = request.form['zone']

    stopwords_list = set(stopwords.words('portuguese'))
    graficos_tabelas = []

    if stopwords_filter == "com":
        palavras = resultado
        titulo = "Com Stopwords"
        graficos_tabelas = gerar_analises_por_zona(analise, palavras, zone_filter, titulo)

    elif stopwords_filter == "sem":
        palavras = resultado[~resultado['palavra'].isin(stopwords_list)]
        titulo = "Sem Stopwords"
        graficos_tabelas = gerar_analises_por_zona(analise, palavras, zone_filter, titulo)

    elif stopwords_filter == "stopwords":
        palavras = resultado[resultado['palavra'].isin(stopwords_list)]
        titulo = "Somente Stopwords"
        graficos_tabelas = gerar_analises_por_zona(analise, palavras, zone_filter, titulo)

    elif stopwords_filter == "todas":
        filtros = [("Com Stopwords", resultado),
                   ("Sem Stopwords", resultado[~resultado['palavra'].isin(stopwords_list)]),
                   ("Somente Stopwords", resultado[resultado['palavra'].isin(stopwords_list)])]
        for titulo, palavras in filtros:
            graficos_tabelas.extend(gerar_analises_por_zona(analise, palavras, zone_filter, titulo))

    # Criar HTML final
    html = ""
    for item in graficos_tabelas:
        html += f"""
        <div class="zona-section">
            <h4>{item['zona']} - {item['titulo']}</h4>
            <img src="{item['grafico']}" class="img-fluid">
            <div>{item['tabela']}</div>
        </div>
        <hr>
        """
    return jsonify({"html": html})

def gerar_analises_por_zona(analise, palavras, zone_filter, titulo):
    zonas = ["Núcleo Central", "Zona Periférica 1", "Zona Periférica 2", "Zona Periférica 3"]
    graficos_tabelas = []

    if zone_filter == "todas":
        for zona in zonas:
            zona_dados = palavras[palavras['zona'] == zona]
            grafico_path = analise.gerar_grafico(zona_dados, titulo, zona)
            graficos_tabelas.append({
                "zona": zona,
                "titulo": titulo,
                "tabela": zona_dados.to_html(classes='table table-striped', index=False),
                "grafico": grafico_path
            })
    else:
        zona_dados = palavras[palavras['zona'] == zone_filter]
        grafico_path = analise.gerar_grafico(zona_dados, titulo, zone_filter)
        graficos_tabelas.append({
            "zona": zone_filter,
            "titulo": titulo,
            "tabela": zona_dados.to_html(classes='table table-striped', index=False),
            "grafico": grafico_path
        })
    return graficos_tabelas

if __name__ == '__main__':
    app.run(debug=True)
