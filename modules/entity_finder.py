from flask import Flask, request, render_template, redirect, url_for
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
import os
import json
from dotenv import load_dotenv
import openai
from openai import OpenAI

###############################################################################
# Carrega variáveis de ambiente e configura o Flask
###############################################################################
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("A chave da API não foi encontrada. Verifique o arquivo .env.")

app = Flask(__name__)

###############################################################################
# Configurações e Inicializações
###############################################################################
openai_client = OpenAI(api_key=openai_api_key)
nlp = spacy.load("pt_core_news_sm")
bert_model = Summarizer()
sia = SentimentIntensityAnalyzer()
geolocator = Nominatim(user_agent="my_flask_app/1.0")


###############################################################################
# Classes de apoio
###############################################################################
class EntityClassifier:
    """
    Classe responsável por gerenciar as etapas de classificação em lote (etapa 1)
    e de busca de imagem (etapa 2), incluindo fallback na SerpAPI caso a OpenAI
    não retorne uma imagem.
    """

    def __init__(self, openai_client):
        self.openai_client = openai_client

    def classificar_em_bloco(self, entidades_unicas):
        """
        Faz uma única chamada à API da OpenAI para classificar uma lista de entidades.
        Retorna um dicionário {entidade: {"tipo":..., "local":...}}.

        Aqui, adicionamos explicitamente a instrução para NÃO retornar duplicados
        no array "resultado", de modo a reforçar a unicidade.
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
        # 1) Tenta pela OpenAI
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


###############################################################################
# Funções auxiliares
###############################################################################
def obter_coordenadas(localizacao):
    """
    Obtém as coordenadas de um local usando geopy. Preservado ipsis litteris.
    """
    try:
        time.sleep(1)  # 1 segundo de delay para evitar exceder limite
        location = geolocator.geocode(localizacao, timeout=10)
        if location:
            return (location.latitude, location.longitude)
        else:
            return None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Erro ao geocodificar {localizacao}: {e}")
        return None


###############################################################################
# Rota principal
###############################################################################
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Botão de Nova Análise
        if request.form.get("nova_analise"):
            print(">>> Botão 'Nova Análise' acionado. Redirecionando para index().")
            return redirect(url_for("index"))

        print(">>> Botão 'Analisar' foi acionado.")
        texto = request.form["texto"]
        print(f">>> Texto recebido: {texto[:50]}..." if texto else ">>> Texto está vazio ou não fornecido.")

        # Identificar entidades com spaCy
        print(">>> Iniciando identificação de entidades com spaCy...")
        doc = nlp(texto)
        entidades = [ent.text for ent in doc.ents]
        print(f">>> Entidades detectadas: {entidades}")

        # Instancia a classe de classificação
        classifier = EntityClassifier(openai_client)

        # ETAPA 1) Classificação em lote (remoção de duplicadas para evitar repetição)
        print(">>> [ETAPA 1] Iniciando classificação em lote das entidades...")
        entidades_unicas = list(set(entidades))
        classificacoes = classifier.classificar_em_bloco(entidades_unicas)

        print(">>> [ETAPA 1] Mapeando resultados para lista final de entidades...")
        entidades_classificadas = []
        for ent in entidades:
            if ent in classificacoes:
                etype = classificacoes[ent]["tipo"]
                elocal = classificacoes[ent]["local"]
                entidades_classificadas.append({"entidade": ent, "tipo": etype, "local": elocal})
            else:
                entidades_classificadas.append({"entidade": ent, "tipo": "desconhecido", "local": None})

        # Separar entidades em pessoas/organizações e localizações
        print(">>> Separando entidades em pessoas/organizações e localizações...")
        pessoas_organizacoes = [e for e in entidades_classificadas if e["tipo"] in ["pessoa", "organização"]]
        localizacoes = [e for e in entidades_classificadas if e["tipo"] == "localização"]

        print(f">>> Pessoas/Organizações: {[p['entidade'] for p in pessoas_organizacoes]}")
        print(f">>> Localizações: {[l['entidade'] for l in localizacoes]}")

        # Análise de sentimento
        print(">>> Iniciando análise de sentimento com NLTK...")
        pessoas_organizacoes_com_sentimento = []
        for entidade_info in pessoas_organizacoes:
            sentimento = sia.polarity_scores(entidade_info["entidade"])
            pessoas_organizacoes_com_sentimento.append({
                **entidade_info,
                "sentimento": sentimento['compound']
            })

        localizacoes_com_sentimento = []
        for entidade_info in localizacoes:
            sentimento = sia.polarity_scores(entidade_info["entidade"])
            localizacoes_com_sentimento.append({
                **entidade_info,
                "sentimento": sentimento['compound']
            })

        # Geração de resumo com BERT
        print(">>> Gerando resumo com BERT Summarizer...")
        resumo = bert_model(texto)

        # Clustering de tópicos
        print(">>> Iniciando clustering de tópicos...")
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

        # Gera mapa com Folium
        print(">>> Gerando mapa com Folium...")
        mapa = folium.Map(location=[-15, -50], zoom_start=4)

        print(">>> Marcando localizações no mapa...")
        for loc in localizacoes_com_sentimento:
            coords = obter_coordenadas(loc["entidade"])
            if coords:
                popup_html = (
                    f"Entidade: {loc['entidade']}<br>"
                    f"Tipo: {loc['tipo']}<br>"
                    f"Local Esperado: {loc['local']}<br>"
                    f"Sentimento: {loc['sentimento']:.2f}"
                )
                folium.Marker(
                    location=coords,
                    tooltip=f"{loc['entidade']} - {loc['tipo']}",
                    popup=popup_html,
                    icon=folium.Icon(color="blue")
                ).add_to(mapa)

        print(">>> Salvando mapa em templates/mapa.html")
        mapa.save("templates/mapa.html")

        # ETAPA 2) Busca de imagens para cada entidade (com fallback)
        print(">>> [ETAPA 2] Iniciando busca de imagens para pessoas/organizações e localizações...")
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

        print(">>> Renderizando template index.html com resultados. Avisando o usuário sobre logs e possíveis erros.")
        return render_template(
            "index.html",
            pessoas=pessoas_organizacoes_com_imagens,
            localizacoes=localizacoes_com_imagens,
            resumo=resumo,
            topicos=topicos_principais,
            texto=texto,
            mapa=True
        )

    # GET
    print(">>> Método GET acessado, retornando template inicial sem dados.")
    return render_template(
        "index.html",
        pessoas=None,
        localizacoes=None,
        resumo=None,
        topicos=None,
        texto=None,
        mapa=False
    )


###############################################################################
# Rota do mapa
###############################################################################
@app.route("/mapa")
def exibir_mapa():
    print(">>> Rota /mapa acessada.")
    return render_template("mapa.html")


###############################################################################
# Execução principal
###############################################################################
if __name__ == "__main__":
    print(">>> Iniciando aplicação Flask em modo debug.")
    app.run(debug=True)
