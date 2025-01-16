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
    e de busca de imagem (etapa 2), utilizando a SerpAPI como abordagem principal.
    """
    def __init__(self, openai_api_key, serp_api_key):
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.nlp = spacy.load("pt_core_news_sm")
        self.bert_model = Summarizer()
        self.sia = SentimentIntensityAnalyzer()
        self.geolocator = Nominatim(user_agent="my_flask_app/1.0")
        self.serp_api_key = serp_api_key
        # Cache para imagens e evitar múltiplas chamadas duplicadas
        self._image_cache = {}

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
            Sintetize estas de maneira a eliminar duplicidades, verifique cada elemento, 
            identifique se este se trata de uma pessoa, organização ou localização e categorize-as.
            1) NÃO retorne entidades duplicadas. Cada entidade só pode aparecer uma única vez.
            2) Responda estritamente em JSON, no formato:
            {
                "resultado": [
                    {"entidade": "...", "tipo": "pessoa|organizacao|localizacao|desconhecido", "local": "... ou null"},
                    ...
                ]
            }
            Analise todas as entidades de entrada, garantindo a unicidade e se assegurando de 
            que cada uma apareça exatamente uma vez no array 'resultado', associada à sua respectiva categorização.
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

    def buscar_imagem_serpapi(self, query, tipo):
        """
        Busca de imagem na SerpAPI, com cache interno e fallback para placeholder.
        """
        # Se já existe em cache, retorna diretamente
        if query in self._image_cache:
            return self._image_cache[query]

        print(f">>> [ETAPA 2] buscar_imagem_serpapi: Buscando imagem para '{query}' como '{tipo}' via SerpAPI...")
        try:
            params = {
                "q": f"{query} {tipo}",
                "tbm": "isch",
                "api_key": self.serp_api_key
            }
            response = requests.get("https://serpapi.com/search", params=params)
            if response.status_code == 200:
                results = response.json()
                if "images_results" in results and len(results["images_results"]) > 0:
                    first_thumb = results["images_results"][0]["thumbnail"]
                    print(f">>> [ETAPA 2] buscar_imagem_serpapi: Imagem encontrada para '{query}': {first_thumb}")
                    self._image_cache[query] = first_thumb
                    return first_thumb
            print(f">>> [ETAPA 2] buscar_imagem_serpapi: Nenhuma imagem encontrada para '{query}'.")
            # Se não encontrou nada, retorna placeholder
            self._image_cache[query] = "/static/img/placeholder.png"
            return self._image_cache[query]
        except Exception as e:
            print(f"Erro na SerpAPI: {e}")
            # Em caso de exceção, retorna placeholder
            self._image_cache[query] = "/static/img/placeholder.png"
            return self._image_cache[query]

def geocode_location(geolocator, query):
    """Tenta geocodar o texto 'query' e retorna (lat, lon) ou None."""
    try:
        location = geolocator.geocode(query)
        # Aguardar um pouco para evitar limite de requisições consecutivas
        time.sleep(0.7)
        if location:
            return (location.latitude, location.longitude)
    except (GeocoderTimedOut, GeocoderServiceError):
        pass
    return None

def process_text(text, classifier):
    """
    Processa o texto para identificar entidades, sumarizar e gerar tópicos.
    Também gera um mapa Folium com base nas entidades localizadas.
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
        image_link = classifier.buscar_imagem_serpapi(entidade_info["entidade"], entidade_info["tipo"])
        pessoas_organizacoes_com_imagens.append({**entidade_info, "imagem": image_link})

    localizacoes_com_imagens = []
    for entidade_info in localizacoes_com_sentimento:
        image_link = classifier.buscar_imagem_serpapi(entidade_info["entidade"], "localização")
        localizacoes_com_imagens.append({**entidade_info, "imagem": image_link})

    # >>> Construir mapa dinamicamente via Folium <<<
    # Posição inicial "genérica" centrada no Brasil
    mapa = folium.Map(location=[-15.0, -50.0], zoom_start=4)
    # Para cada local, tentar geocodar e adicionar marker
    for loc in localizacoes_com_imagens:
        coords = geocode_location(classifier.geolocator, loc["entidade"])
        if coords:
            popup_str = (f"Entidade: {loc['entidade']}<br>"
                         f"Tipo: {loc['tipo']}<br>"
                         f"Local Esperado: {loc['local']}<br>"
                         f"Sentimento: {loc['sentimento']:.2f}")
            folium.Marker(
                location=coords,
                popup=popup_str,
                tooltip=f"{loc['entidade']} - {loc['tipo']}"
            ).add_to(mapa)

    # Gera HTML do mapa para embutir no front-end
    map_html = mapa._repr_html_()

    return {
        "pessoas": pessoas_organizacoes_com_imagens,
        "localizacoes": localizacoes_com_imagens,
        "resumo": resumo,
        "topicos": topicos_principais,
        "map_html": map_html  # HTML do mapa gerado
    }
