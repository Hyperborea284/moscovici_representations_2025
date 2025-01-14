import spacy
from summarizer import Summarizer
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import numpy as np
import folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
import requests
import json
from openai import OpenAI

class EntityClassifier:
    """
    Classe responsável por gerenciar as etapas de classificação em lote (etapa 1)
    e de busca de imagem (etapa 2), incluindo fallback na SerpAPI caso a OpenAI
    não retorne uma imagem.
    """

    def __init__(self, openai_api_key):
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.nlp = spacy.load("pt_core_news_sm")
        self.bert_model = Summarizer()
        self.sia = SentimentIntensityAnalyzer()
        self.geolocator = Nominatim(user_agent="my_flask_app/1.0")

    def classificar_em_bloco(self, entidades_unicas):
        """
        Faz uma única chamada à API da OpenAI para classificar uma lista de entidades.
        Retorna um dicionário {entidade: {"tipo":..., "local":...}}.
        """
        print(">>> [ETAPA 1] classificar_entidades_em_bloco: Iniciando classificação em lote...")

        try:
            # Prompt que enfatiza a unicidade das entidades
            prompt_str = """
            Você receberá uma lista de entidades (pessoas, organizações ou localizações).
            1) NÃO retorne duplicados. Cada entidade só deve aparecer uma única vez.
            2) Responda estritamente em JSON, no formato:
            {
                "resultado": [
                    {"entidade": "...", "tipo": "pessoa|organizacao|localizacao|desconhecido", "local": "... ou null"},
                    ...
                ]
            }
            Liste todas as entidades de entrada, garantindo que cada uma apareça exatamente uma vez no array 'resultado'.
            """

            prompt_entidades = "Lista de entidades:\n" + "\n".join([f"- {e}" for e in entidades_unicas])
            prompt_final = prompt_str + "\n\n" + prompt_entidades

            print(">>> [ETAPA 1] classificar_entidades_em_bloco: Enviando para OpenAI GPT-4...")
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt_final}]
            )
            conteudo = response.choices[0].message.content
            print("\n--- Resposta da API (etapa 1) ---")
            print(conteudo)

            data = json.loads(conteudo)
            classif_dict = {}
            for item in data.get("resultado", []):
                ent = item.get("entidade", "")
                tipo_raw = item.get("tipo", "desconhecido")
                loc_raw = item.get("local", None)

                tipo_map = {
                    "pessoa": "pessoa",
                    "organizacao": "organização",
                    "localizacao": "localização",
                    "desconhecido": "desconhecido"
                }
                tipo_final = tipo_map.get(tipo_raw, "desconhecido")
                loc_final = loc_raw if loc_raw != "null" else None
                classif_dict[ent] = {
                    "tipo": tipo_final,
                    "local": loc_final
                }

            print(">>> [ETAPA 1] Classificação em lote concluída.")
            return classif_dict

        except Exception as e:
            print(f"Erro na classificação em bloco: {e}")
            return {}

    def buscar_imagem(self, query, tipo):
        """
        Tenta obter um link de imagem da OpenAI (etapa 2). Em caso de falha ou erro
        no conteúdo retornado, faz o fallback para a SerpAPI.
        """
        print(f">>> [ETAPA 2] buscar_imagem: Buscando imagem para '{query}' como '{tipo}' usando GPT-4...")
        try:
            prompt = f"""
            Você é um sistema que retorna links de imagens.
            Entrada: '{query}' (tipo: {tipo})
            Retorne estritamente em JSON, no formato:
            {{
                "imagem_url": "https://exemplo-de-imagem.jpg"
            }}
            Dê preferência a links representativos e recentes.
            """
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            conteudo = response.choices[0].message.content
            print("\n--- Resposta da API (etapa 2) ---")
            print(conteudo)

            data = json.loads(conteudo)
            imagem_url = data.get("imagem_url", None)
            if not imagem_url or not imagem_url.startswith("http"):
                print(f">>> [ETAPA 2] buscar_imagem: Nenhum link válido via OpenAI; fallback para SerpAPI.")
                return self.buscar_imagem_serpapi(query, tipo)

            print(f">>> [ETAPA 2] buscar_imagem: Link retornado para '{query}': {imagem_url}")
            return imagem_url

        except Exception as e:
            print(f"Erro ao buscar imagem pela OpenAI: {e}")
            print(">>> [ETAPA 2] buscando imagem pela SerpAPI como fallback.")
            return self.buscar_imagem_serpapi(query, tipo)

    def buscar_imagem_serpapi(self, query, tipo):
        """
        Fallback para busca de imagem na SerpAPI.
        """
        print(f">>> [FALLBACK] buscar_imagem_serpapi: Buscando imagem para '{query}' como '{tipo}' via SerpAPI...")
        try:
            params = {
                "q": f"{query} {tipo}",
                "tbm": "isch",
                "api_key": "sua_chave_serpapi_aqui"
            }
            response = requests.get("https://serpapi.com/search", params=params)
            if response.status_code == 200:
                results = response.json()
                if "images_results" in results and len(results["images_results"]) > 0:
                    first_thumb = results["images_results"][0]["thumbnail"]
                    print(f">>> [FALLBACK] buscar_imagem_serpapi: Imagem encontrada para '{query}': {first_thumb}")
                    return first_thumb
            print(f">>> [FALLBACK] buscar_imagem_serpapi: Nenhuma imagem encontrada para '{query}'.")
            return None
        except Exception as e:
            print(f"Erro na SerpAPI: {e}")
            return None

def process_text(text, classifier):
    """
    Processa o texto para identificar entidades, sumarizar e gerar tópicos.
    """
    print(">>> Iniciando processamento de texto...")
    doc = classifier.nlp(text)
    entidades = [ent.text for ent in doc.ents]
    print(f">>> Entidades detectadas: {entidades}")

    # Classificação em lote
    entidades_unicas = list(set(entidades))
    classificacoes = classifier.classificar_em_bloco(entidades_unicas)

    entidades_classificadas = []
    for ent in entidades:
        if ent in classificacoes:
            etype = classificacoes[ent]["tipo"]
            elocal = classificacoes[ent]["local"]
            entidades_classificadas.append({"entidade": ent, "tipo": etype, "local": elocal})
        else:
            entidades_classificadas.append({"entidade": ent, "tipo": "desconhecido", "local": None})

    # Separar entidades em pessoas/organizações e localizações
    pessoas_organizacoes = [e for e in entidades_classificadas if e["tipo"] in ["pessoa", "organização"]]
    localizacoes = [e for e in entidades_classificadas if e["tipo"] == "localização"]

    # Análise de sentimento
    pessoas_organizacoes_com_sentimento = []
    for entidade_info in pessoas_organizacoes:
        sentimento = classifier.sia.polarity_scores(entidade_info["entidade"])
        pessoas_organizacoes_com_sentimento.append({
            **entidade_info,
            "sentimento": sentimento['compound']
        })

    localizacoes_com_sentimento = []
    for entidade_info in localizacoes:
        sentimento = classifier.sia.polarity_scores(entidade_info["entidade"])
        localizacoes_com_sentimento.append({
            **entidade_info,
            "sentimento": sentimento['compound']
        })

    # Geração de resumo com BERT
    resumo = classifier.bert_model(text)

    # Clustering de tópicos
    frases = [sent.text for sent in doc.sents]
    if len(frases) > 1:
        vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        X = vectorizer.fit_transform(frases)
        num_clusters = min(3, len(frases))
        kmeans = KMeans(n_clusters=num_clusters, random_state=42)
        kmeans.fit(X)
        clusters = kmeans.labels_

        topicos = {}
        for i, c in enumerate(clusters):
            if c not in topicos:
                topicos[c] = []
            topicos[c].append(frases[i])

        topicos_principais = []
        for c in topicos:
            centroide = np.mean(X[clusters == c], axis=0)
            indice_representante = np.argmin(
                np.linalg.norm(X[clusters == c] - centroide, axis=1)
            )
            topicos_principais.append(topicos[c][indice_representante])
    else:
        topicos_principais = ["Não há frases suficientes para clustering."]

    # Busca de imagens para cada entidade
    pessoas_organizacoes_com_imagens = []
    for entidade_info in pessoas_organizacoes_com_sentimento:
        if entidade_info["tipo"] == "pessoa":
            image_link = classifier.buscar_imagem(entidade_info["entidade"], "pessoa")
        elif entidade_info["tipo"] == "organização":
            image_link = classifier.buscar_imagem(entidade_info["entidade"], "organização")
        else:
            image_link = None
        pessoas_organizacoes_com_imagens.append({**entidade_info, "imagem": image_link})

    localizacoes_com_imagens = []
    for entidade_info in localizacoes_com_sentimento:
        image_link = classifier.buscar_imagem(entidade_info["entidade"], "localização")
        localizacoes_com_imagens.append({**entidade_info, "imagem": image_link})

    return {
        "pessoas": pessoas_organizacoes_com_imagens,
        "localizacoes": localizacoes_com_imagens,
        "resumo": resumo,
        "topicos": topicos_principais
    }