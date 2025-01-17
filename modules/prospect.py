from openai import OpenAI
from summarizer import Summarizer
import os
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import numpy as np
from goose3 import Goose
import json
import spacy
import time  # Para gerar a timestamp
from sentence_transformers import SentenceTransformer
import webbrowser

# Carregar o modelo de linguagem do spaCy
nlp = spacy.load("pt_core_news_sm")

class TextProcessor:
    """
    Classe responsável por processar o texto, gerar o resumo e extrair os tópicos.
    """
    def __init__(self, text):
        self.text = text
        self.bert_model = Summarizer()
        self.resumo = None
        self.topicos = None

    def process_text(self):
        """Gera o resumo e os tópicos a partir do texto."""
        print("Processando texto para gerar resumo e tópicos...")
        # Gerar resumo usando BERT Summarizer
        self.resumo = self.bert_model(self.text)
        print("Resumo gerado com sucesso.")

        # Processar o texto em frases usando spaCy
        doc = nlp(self.text)
        frases = [sent.text for sent in doc.sents]
        print(f"Texto dividido em {len(frases)} frases.")

        # Clustering de tópicos com Sentence-BERT
        if len(frases) > 1:
            print("Realizando clustering de tópicos com Sentence-BERT...")
            # Carregar o modelo Sentence-BERT
            model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
            # Gerar embeddings das frases
            sentence_embeddings = model.encode(frases)
            # Aplicar K-Means nos embeddings
            num_clusters = min(3, len(frases))
            kmeans = KMeans(n_clusters=num_clusters, random_state=42)
            clusters = kmeans.fit_predict(sentence_embeddings)

            self.topicos = {}
            for i, c in enumerate(clusters):
                if c not in self.topicos:
                    self.topicos[c] = []
                self.topicos[c].append(frases[i])

            print("Clustering de tópicos concluído.")
        else:
            self.topicos = {"0": ["Não há frases suficientes para clustering."]}
            print("Número insuficiente de frases para clustering.")

        return self.resumo, self.topicos

class ScenarioClassifier:
    """
    Classe responsável por gerar cenários (imediato, curto, médio e longo prazos),
    usando as informações de resumo, tópicos e texto original.
    """
    def __init__(self, resumo, topicos, combined_text):
        # Carregar variáveis de ambiente
        load_dotenv()
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("A chave da API não foi encontrada. Verifique o arquivo .env.")

        self.client = OpenAI(api_key=openai_api_key)
        self.resumo = resumo
        self.topicos = topicos
        self.combined_text = combined_text

    def generate_prompt(self):
        """Gera o prompt final para a OpenAI."""
        print("Gerando prompt para a OpenAI...")
        prompt_final = f'''
        Você é um assistente que receberá esta lista de tópicos {self.topicos} elaborada por
        sklearn e sentence-BERT, um resumo {self.resumo} elaborado por bert-summarizer, 
        e os textos originais {self.combined_text}. Partindo daí, você deverá retornar
        um arquivo json estruturado prevendo cenários que se organizam seguindo
        este diagrama de quatro linhas por três colunas:

        Linhas:  - cenários: imediato(IM), curto(CT), médio(MD) e longo(LG) prazos
        Colunas: - cenários: menos provável(C+P), cenário normal(CN), cenário mais provável(C+P)

        O JSON deve seguir exatamente esta estrutura:

        {{
            "cenarios": {{
                "imediato": {{
                    "menos_probavel": "...",
                    "normal": "...",
                    "mais_probavel": "..."
                }},
                "curto": {{
                    "menos_probavel": "...",
                    "normal": "...",
                    "mais_probavel": "..."
                }},
                "medio": {{
                    "menos_probavel": "...",
                    "normal": "...",
                    "mais_probavel": "..."
                }},
                "longo": {{
                    "menos_probavel": "...",
                    "normal": "...",
                    "mais_probavel": "..."
                }}
            }}
        }}

        Certifique-se de que o JSON retornado siga exatamente esta estrutura, substituindo as 
        descrições genéricas por previsões baseadas nos tópicos, resumo e textos fornecidos.
        '''
        print("Prompt gerado com sucesso.")
        return prompt_final

    def call_openai_api(self, prompt):
        """Chama a API da OpenAI com o prompt fornecido."""
        print("Chamando a API da OpenAI...")
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",  # Modelo hipotético, caso queira GPT-4
            messages=[{"role": "user", "content": prompt}]
        )
        conteudo = response.choices[0].message.content
        print("Resposta da API recebida com sucesso.")
        return conteudo

    def generate_html(self, conteudo):
        """
        Gera um HTML com o conteúdo retornado pelo prompt, os tópicos e o resumo,
        porém, nesta versão convergente, não abre automaticamente no navegador.
        """
        print("Gerando HTML dos cenários...")
        # Parse o JSON retornado
        try:
            cenarios = json.loads(conteudo)
            print("JSON parseado com sucesso.")
        except json.JSONDecodeError:
            cenarios = {"erro": "Formato JSON inválido retornado pelo prompt."}
            print("Erro ao parsear o JSON.")

        # Acessar os cenários corretamente
        if "cenarios" in cenarios:
            cenarios_data = cenarios["cenarios"]
        else:
            cenarios_data = {
                "imediato": {"menos_probavel": "", "normal": "", "mais_probavel": ""},
                "curto": {"menos_probavel": "", "normal": "", "mais_probavel": ""},
                "medio": {"menos_probavel": "", "normal": "", "mais_probavel": ""},
                "longo": {"menos_probavel": "", "normal": "", "mais_probavel": ""},
            }

        # Montar HTML resultante (sem salvar em arquivo nem abrir browser)
        html_content = f"""
        <h2>Cenários Gerados</h2>
        <h3>Resumo</h3>
        <p>{self.resumo}</p>
        <h3>Tópicos</h3>
        <ul>
            {"".join([f"<li>{', '.join(topico)}</li>" for topico in self.topicos.values()])}
        </ul>
        <h3>Cenários</h3>
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th></th>
                    <th>Menos Provável (C+P)</th>
                    <th>Cenário Normal (CN)</th>
                    <th>Mais Provável (C+P)</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>Imediato (IM)</strong></td>
                    <td>{cenarios_data.get("imediato", {}).get("menos_probavel", "")}</td>
                    <td>{cenarios_data.get("imediato", {}).get("normal", "")}</td>
                    <td>{cenarios_data.get("imediato", {}).get("mais_probavel", "")}</td>
                </tr>
                <tr>
                    <td><strong>Curto Prazo (CT)</strong></td>
                    <td>{cenarios_data.get("curto", {}).get("menos_probavel", "")}</td>
                    <td>{cenarios_data.get("curto", {}).get("normal", "")}</td>
                    <td>{cenarios_data.get("curto", {}).get("mais_probavel", "")}</td>
                </tr>
                <tr>
                    <td><strong>Médio Prazo (MD)</strong></td>
                    <td>{cenarios_data.get("medio", {}).get("menos_probavel", "")}</td>
                    <td>{cenarios_data.get("medio", {}).get("normal", "")}</td>
                    <td>{cenarios_data.get("medio", {}).get("mais_probavel", "")}</td>
                </tr>
                <tr>
                    <td><strong>Longo Prazo (LG)</strong></td>
                    <td>{cenarios_data.get("longo", {}).get("menos_probavel", "")}</td>
                    <td>{cenarios_data.get("longo", {}).get("normal", "")}</td>
                    <td>{cenarios_data.get("longo", {}).get("mais_probavel", "")}</td>
                </tr>
            </tbody>
        </table>
        """

        return html_content, cenarios  # Retorna o HTML e o dicionário JSON parseado

def scrape_links(links):
    """
    Função para raspar conteúdo de uma lista de links. 
    Retorna uma tupla (combined_text, bad_links):
      - combined_text: texto concatenado de todos os artigos bem-sucedidos
      - bad_links: lista de links que falharam ou retornaram texto vazio
    """
    print("Raspando links...")
    combined_text = ""
    g = Goose()
    bad_links = []

    while links:
        link = links.pop(0).strip()
        try:
            print(f"Processando link: {link}")
            article = g.extract(url=link)
            text = article.cleaned_text if article else ""
            if not text.strip():
                bad_links.append(link)
                print(f"[SCRAPER] Link sem texto ou vazio: {link}")
            else:
                combined_text += text + "\n"
                print(f"[SCRAPER] Link processado com sucesso: {link}")
        except Exception as e:
            print(f"[SCRAPER] Erro ao processar link {link}: {e}")
            bad_links.append(link)

    print("Raspagem de links concluída.")
    return combined_text, bad_links

# A seguir, caso se deseje rodar standalone (exemplo):
if __name__ == "__main__":
    print("Por favor, insira uma lista de links para serem raspados (separados por vírgula):")
    links_input = input("Links: ")
    links_list = links_input.split(",") if links_input.strip() else []

    combined_text, bad_links = scrape_links(links_list)
    print("\nTexto combinado (primeiros 500 chars):")
    print(combined_text[:500] + "...")

    print("\nLinks problemáticos:", bad_links)

    # Processar texto
    text_processor = TextProcessor(combined_text)
    resumo, topicos = text_processor.process_text()

    # Classificar entidades e gerar cenários
    classifier = EntityClassifier(resumo, topicos, combined_text)
    prompt = classifier.generate_prompt()
    conteudo = classifier.call_openai_api(prompt)

    # Gera o HTML sem abrir browser
    html_resultado, cenarios_dict = classifier.generate_html(conteudo)
    print("\nHTML resultante:\n")
    print(html_resultado)
    print("\nCenários (JSON):")
    print(json.dumps(cenarios_dict, indent=4, ensure_ascii=False))
