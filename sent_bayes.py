import matplotlib
matplotlib.use('Agg')  # Usar backend não-GUI

import itertools
import nltk
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime
from pathlib import Path
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.stem import RSLPStemmer
from nltk.probability import FreqDist
from base import raiva, tristeza, surpresa, medo, desgosto, alegria
import re
from time import sleep
from threading import Thread
from queue import Queue
from dist_normal import analyze_data, detect_outliers, plot_distribution

class SentimentAnalyzer:
    """
    Classe para análise de sentimentos em textos utilizando processamento de linguagem natural.
    """
    def __init__(self, output_dir='./static/generated_images'):
        """Inicializa o analisador de sentimentos, configurando o diretório de saída."""
        print("Reinicializando SentimentAnalyzer...")
        nltk.download('punkt')
        nltk.download('stopwords')
        self.stopwordsnltk = stopwords.words('portuguese')
        self.emotions_funcs = {
            'raiva': raiva,
            'tristeza': tristeza,
            'surpresa': surpresa,
            'medo': medo,
            'desgosto': desgosto,
            'alegria': alegria,
        }
        self.generated_images_dir = Path(output_dir)
        self.generated_images_dir.mkdir(parents=True, exist_ok=True)
        self.classificador = None
        self.palavrasunicas = None

    def reset_analyzer(self):
        """Reinicializa o analisador de sentimentos."""
        print("Resetando analisador...")
        self.classificador = None
        self.palavrasunicas = None

    def deactivate_analyzer(self):
        """Desativa o analisador de sentimentos."""
        print("Desativando SentimentAnalyzer...")
        self.classificador = None
        self.palavrasunicas = None

    @staticmethod
    def count_paragraphs(text: str) -> list:
        """Conta parágrafos no texto, retornando apenas os parágrafos não vazios."""
        print("Contando parágrafos...")
        paragraphs = text.split('\n\n')
        return [p for p in paragraphs if p.strip()]

    @staticmethod
    def count_sentences(text: str) -> list:
        """Conta frases no texto utilizando o tokenizador de sentenças do NLTK."""
        print("Contando frases...")
        return sent_tokenize(text, language='portuguese')

    @staticmethod
    def is_valid_html(content: str) -> bool:
        """Verifica se o conteúdo é um HTML válido."""
        print("Verificando se o conteúdo é HTML válido...")
        return bool(re.search(r'<h1>Texto Analisado</h1>.*?<div.*?>.*?</div>', content, re.DOTALL))

    def process_document(self, filepath: str) -> tuple:
        """Processa um documento para separar em parágrafos e frases."""
        print("Processando documento...")
        with open(filepath, 'r', encoding='utf-8') as file:
            text = file.read()
        paragraphs = self.count_paragraphs(text)
        sentences = self.count_sentences(text)
        return paragraphs, sentences

    def process_text(self, text: str) -> tuple:
        """Processa um texto para separar em parágrafos e frases."""
        print("Processando texto...")
        text = text.replace('\r\n', '\n')
        paragraphs = self.count_paragraphs(text)
        sentences = self.count_sentences(text)
        return paragraphs, sentences

    def analyze_paragraphs(self, paragraphs: list) -> tuple:
        """Analisa parágrafos para obter pontuações de sentimentos."""
        print("Analisando parágrafos...")
        scores_list = []
        paragraph_end_indices = []
        sentence_count = 0
        for paragraph in paragraphs:
            sents = self.count_sentences(paragraph)
            for sentence in sents:
                scores = self.classify_emotion(sentence)
                scores_list.append(scores)
            sentence_count += len(sents)
            paragraph_end_indices.append(sentence_count)
        return scores_list, paragraph_end_indices

    def aplicastemmer(self, texto: list) -> list:
        """Aplica um algoritmo de stemming às palavras do texto."""
        print("Aplicando stemming...")
        stemmer = RSLPStemmer()
        frasesstemming = []
        for (palavras, emocao) in texto:
            comstemming = [str(stemmer.stem(p)) for p in word_tokenize(palavras) if p not in self.stopwordsnltk]
            frasesstemming.append((comstemming, emocao))
        return frasesstemming

    def buscapalavras(self, frases: list) -> list:
        """Busca todas as palavras fornecidas nas frases."""
        print("Buscando palavras nas frases...")
        all_words = []
        for (words, _) in frases:
            all_words.extend(words)
        return all_words

    def buscafrequencia(self, palavras: list) -> FreqDist:
        """Calcula a frequência das palavras fornecidas."""
        print("Calculando frequência das palavras...")
        return FreqDist(palavras)

    def buscapalavrasunicas(self, frequencia: FreqDist) -> list:
        """Busca palavras únicas a partir da frequência de palavras."""
        print("Buscando palavras únicas...")
        return list(frequencia.keys())

    def extratorpalavras(self, documento: list) -> dict:
        """Extrai palavras do documento comparando com palavras únicas."""
        print("Extraindo palavras do documento...")
        doc = set(documento)
        return {word: (word in doc) for word in self.palavrasunicas}

    def classify_emotion(self, sentence: str) -> np.array:
        """Classifica uma frase para cada emoção usando um Classificador Bayesiano Ingênuo."""
        print("Classificando emoção na frase...")
        if not self.classificador:
            print("Treinando classificador Bayesiano Ingênuo...")
            training_base = sum((self.emotions_funcs[emotion]() for emotion in self.emotions_funcs), [])
            frasesstemming = self.aplicastemmer(training_base)
            palavras = self.buscapalavras(frasesstemming)
            frequencia = self.buscafrequencia(palavras)
            self.palavrasunicas = self.buscapalavrasunicas(frequencia)
            complete_base = nltk.classify.apply_features(lambda doc: self.extratorpalavras(doc), frasesstemming)
            self.classificador = nltk.NaiveBayesClassifier.train(complete_base)

        test_stemming = [RSLPStemmer().stem(p) for p in word_tokenize(sentence)]
        new_features = self.extratorpalavras(test_stemming)
        result = self.classificador.prob_classify(new_features)
        return np.array([result.prob(emotion) for emotion in self.emotions_funcs.keys()])

    def generate_html_content(self, timestamp: str, paragraphs: list, sentences: list, analyze_only=False) -> str:
        """Gera HTML dividido em partes fixas e dinâmicas."""
        base_path = './static/generated_images/'
    
        html_paragraphs = []
        sentence_counter = 1
        for paragraph in paragraphs:
            marked_paragraph = paragraph
            for sentence in sentences:
                if sentence in marked_paragraph:
                    marked_paragraph = marked_paragraph.replace(
                        sentence, f'{sentence} <span style="color:red;">[{sentence_counter}]</span>'
                    )
                    sentence_counter += 1
            html_paragraphs.append(f'<p>{marked_paragraph}</p>')
    
        if not analyze_only:
            # Geração da parte fixa (Texto Analisado, Timestamp, Contagem)
            html_fixed = f"""
                <h1>Texto Analisado</h1>
                <div id="analyzedText" style='border:1px solid black; padding:10px;'>{''.join(html_paragraphs)}</div>
                <h1>Data e Hora da Análise</h1>
                <div id="timestamp" style='border:1px solid black; padding:10px;'>{timestamp}</div>
                <h1>Número de Parágrafos e Frases</h1>
                <div id="counts" style='border:1px solid black; padding:10px;'>Parágrafos: {len(paragraphs)}, Frases: {len(sentences)}</div>
            """
            return html_fixed
    
        # Geração da parte dinâmica (Gráficos)
        html_dynamic = f"""
            <h1>Gráficos Gerais</h1>
            <div style='border:1px solid black; padding:10px;'>
                <img src='{base_path}pie_chart_{timestamp}.png' alt='Gráfico de pizza de sentimentos'>
                <img src='{base_path}bar_chart_{timestamp}.png' alt='Gráfico de barras de sentimentos'>
            </div>
        """
        emotions = list(self.emotions_funcs.keys())
        for emotion in emotions:
            html_dynamic += f"""
                <h2>{emotion.capitalize()}</h2>
                <div style='border:1px solid black; padding:10px;'>
                    <img src='{base_path}{emotion}_score_{timestamp}.png' alt='Gráfico de linhas para {emotion}'>
                    <img src='{base_path}{emotion}_distribution_{timestamp}.png' alt='Distribuição Normal para {emotion}'>
                </div>
            """
        return html_dynamic

    def plot_individual_emotion_charts(self, scores_list, paragraph_end_indices, timestamp):
        """Plota gráficos de linhas para cada emoção."""
        emotions = list(self.emotions_funcs.keys())
        paths = []

        for i, emotion in enumerate(emotions):
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot([score[i] for score in scores_list], label=f'{emotion} pontuações')
            for end_idx in paragraph_end_indices:
                ax.axvline(x=end_idx, color='grey', linestyle='--', label='Fim do Parágrafo' if end_idx == paragraph_end_indices[0] else "")
            ax.legend(loc='upper right')
            ax.set_title(f'Evolução da Pontuação: {emotion}')
            ax.set_xlabel('Contagem de frases')
            ax.set_ylabel('Pontuações')
            plt.tight_layout()

            filepath = self.generated_images_dir / f'{emotion}_score_{timestamp}.png'
            plt.savefig(filepath)
            paths.append(str(filepath))
            plt.close()

        return paths

    def plot_pie_chart(self, scores_list, timestamp):
        """Plota um gráfico de pizza da distribuição de emoções."""
        labels = list(self.emotions_funcs.keys())
        sizes = [np.mean([score[idx] for score in scores_list]) for idx in range(len(labels))]
        plt.figure(figsize=(8, 8))
        plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
        plt.title('Proporção de Cada Sentimento')
    
        filepath = self.generated_images_dir / f'pie_chart_{timestamp}.png'
        plt.savefig(filepath)
        plt.close()
        return str(filepath)

    def plot_bar_chart(self, scores_list, timestamp):
        """Plota um gráfico de barras das frequências de emoções."""
        labels = list(self.emotions_funcs.keys())
        sizes = [np.sum([score[idx] for score in scores_list]) for idx in range(len(labels))]
        plt.figure(figsize=(10, 6))
        plt.bar(labels, sizes, color='purple', edgecolor='black')
        plt.title('Frequência de Emoções Detectadas')
        plt.xlabel('Emoção')
        plt.ylabel('Frequência')

        filepath = self.generated_images_dir / f'bar_chart_{timestamp}.png'
        plt.savefig(filepath)
        plt.close()
        return str(filepath)

    def execute_analysis_text(self, text):
        """Realiza a análise de sentimentos e retorna os gráficos gerados."""
        if not text:  # Verifica se o texto é None ou vazio
            raise ValueError("Nenhum texto fornecido para análise.")

        self.reset_analyzer()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        paragraphs, sentences = self.process_text(text)
        scores_list, paragraph_end_indices = self.analyze_paragraphs(paragraphs)

        score_paths = self.plot_individual_emotion_charts(scores_list, paragraph_end_indices, timestamp)
        pie_chart_path = self.plot_pie_chart(scores_list, timestamp)
        bar_chart_path = self.plot_bar_chart(scores_list, timestamp)

        html_fixed = self.generate_html_content(timestamp, paragraphs, sentences, analyze_only=False)
        html_dynamic = self.generate_html_content(timestamp, paragraphs, sentences, analyze_only=True)

        return html_fixed, html_dynamic

    def generate_html_content_process(self, queue: Queue, timestamp: str, paragraphs: list, sentences: list):
        """Gera conteúdo HTML fixo e dinâmico em processos separados e adiciona ao Queue."""
        print("Gerando conteúdo HTML no processo separado...")
        html_fixed = self.generate_html_content(timestamp, paragraphs, sentences, analyze_only=False)
        html_dynamic = self.generate_html_content(timestamp, paragraphs, sentences, analyze_only=True)
        queue.put((html_fixed, html_dynamic))