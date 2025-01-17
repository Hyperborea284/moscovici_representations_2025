import re
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import time
import nltk
from nltk.corpus import stopwords


class RepresentacaoSocial:
    def __init__(self, textos, aplicar_filtro=True):
        """
        Inicializa a classe com os textos e prepara os dados.
        :param textos: Lista de textos para análise.
        :param aplicar_filtro: Define se o filtro de números e emojis será aplicado.
        """
        self.textos = [self._limpar_pontuacao(texto) for texto in textos]
        self.data = self._preparar_dados(aplicar_filtro=aplicar_filtro)

    def _limpar_pontuacao(self, texto):
        """
        Remove pontuação de um texto.
        :param texto: Texto de entrada.
        :return: Texto sem pontuação.
        """
        return re.sub(r'[^\w\s]', '', texto)

    def _remover_numeros_emojis(self, texto):
        """
        Remove números, numerais ordinais e emojis de um texto.
        :param texto: Texto de entrada.
        :return: Texto sem números, numerais ordinais e emojis.
        """
        texto = re.sub(r'\b\d+\b', '', texto)  # Remove números inteiros
        texto = re.sub(r'\b\d+(?:st|nd|rd|th)\b', '', texto)  # Remove numerais ordinais
        texto = re.sub(r'[^\w\s,]', '', texto)  # Remove emojis
        return texto

    def _preparar_dados(self, aplicar_filtro=True):
        """
        Prepara os dados para análise.
        :param aplicar_filtro: Define se o filtro de números e emojis será aplicado.
        :return: DataFrame com palavras e suas ordens.
        """
        palavras = []
        ordem = []
        for i, texto in enumerate(self.textos):
            texto_limpo = self._remover_numeros_emojis(texto) if aplicar_filtro else texto
            for j, palavra in enumerate(texto_limpo.split(), start=1):
                palavras.append(palavra.lower())
                ordem.append(j)
        return pd.DataFrame({'palavra': palavras, 'ordem': ordem})

    def calcular_frequencia_ome(self):
        """
        Calcula frequência, OME (Ordem Média de Evocação) e determina as zonas.
        :return: DataFrame com os resultados.
        """
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

    def gerar_grafico(self, df, filtro, zona, upload_folder):
        """
        Gera um gráfico baseado nos dados filtrados.
        :param df: DataFrame com os dados filtrados.
        :param filtro: Tipo de filtro aplicado.
        :param zona: Zona correspondente.
        :param upload_folder: Caminho para salvar o gráfico.
        :return: Caminho do gráfico gerado.
        """
        plt.figure(figsize=(6, 4))
        plt.scatter(df['frequencia'], df['OME'])
        plt.title(f"Gráfico para {filtro.capitalize()} Stopwords e {zona}")
        plt.xlabel('Frequência')
        plt.ylabel('OME')
        filepath = os.path.join(upload_folder, f"grafico_{time.time()}.png")
        plt.savefig(filepath)
        plt.close()
        return filepath


def process_representacao_social(text, request_form, upload_folder):
    """
    Processa a análise de Representação Social.
    :param text: Texto para análise.
    :param request_form: Formulário com os filtros.
    :param upload_folder: Caminho para salvar arquivos gerados.
    :return: Dicionário com { 'html': ..., 'caminhos_imagens': ..., 'conteudos_tabelas': ... }
    """
    textos = nltk.sent_tokenize(text)
    aplicar_filtro = request_form.get('extra_filter', 'nao') == 'sim'
    analise = RepresentacaoSocial(textos, aplicar_filtro=aplicar_filtro)
    resultado = analise.calcular_frequencia_ome()

    # ------ Ajustes no filtro de stopwords ------
    stopwords_filter = request_form.get('stopwords', 'com')
    stopwords_list = set(stopwords.words('portuguese'))

    if stopwords_filter == "com":
        palavras = resultado
    elif stopwords_filter == "sem":
        palavras = resultado[~resultado['palavra'].isin(stopwords_list)]
    elif stopwords_filter == "stopwords":
        palavras = resultado[resultado['palavra'].isin(stopwords_list)]
    else:
        palavras = resultado

    # ------ Ajustes no filtro de zonas ------
    zone_filter = request_form.get('zone', 'todas')
    zonas = ["Núcleo Central", "Zona Periférica 1", "Zona Periférica 2", "Zona Periférica 3"]
    graficos_tabelas = []

    if zone_filter == "todas":
        for zona in zonas:
            zona_dados = palavras[palavras['zona'] == zona]
            grafico_path = analise.gerar_grafico(zona_dados, stopwords_filter, zona, upload_folder)
            html_tabela = zona_dados.to_html(classes='table table-striped', index=False)
            graficos_tabelas.append({
                "zona": zona,
                "tabela": html_tabela,
                "grafico": grafico_path
            })
    else:
        zona_dados = palavras[palavras['zona'] == zone_filter]
        grafico_path = analise.gerar_grafico(zona_dados, stopwords_filter, zone_filter, upload_folder)
        html_tabela = zona_dados.to_html(classes='table table-striped', index=False)
        graficos_tabelas.append({
            "zona": zone_filter,
            "tabela": html_tabela,
            "grafico": grafico_path
        })

    html = ""
    caminhos_imagens = []
    conteudos_tabelas = []

    for item in graficos_tabelas:
        html += f"""
        <div class="zona-section">
            <h4>{item['zona']}</h4>
            <img src="{item['grafico']}" style="width: 100%; margin-bottom: 10px;" class="img-fluid">
            <div>{item['tabela']}</div>
        </div>
        <hr>
        """
        caminhos_imagens.append(item['grafico'])
        conteudos_tabelas.append(item['tabela'])

    return {
        "html": html,
        "caminhos_imagens": ";".join(caminhos_imagens),
        "conteudos_tabelas": ";".join(conteudos_tabelas)
    }
