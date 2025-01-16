from openai import OpenAI
from summarizer import Summarizer
import os
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import requests
from goose3 import Goose

class EntityClassifier:
    """
    Classe responsável por gerenciar as etapas de classificação em lote (etapa 1)
    e de busca de imagem (etapa 2), utilizando a SerpAPI como abordagem principal.
    """
    def __init__(self, text):
        # Carregar variáveis de ambiente
        load_dotenv()
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("A chave da API não foi encontrada. Verifique o arquivo .env.")

        self.client = OpenAI(api_key=openai_api_key)

        self.bert_model = Summarizer()
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

        prompt_final = f'''
        Você é um assistente que receberá esta lista de tópicos {topicos} elaborada por
        sklearn, um resumo {resumo} elaborado bert-summarizer, e uma linha do tempo em 
        xml compativel com o timeline 2.9.0. Partindo dai, você deverá retornar
        um arquivo json estruturado prevendo cenarios que se organizam seguindo
        este diagrama de quatro linhas por tres colunas
        Linhas:  - cenários: imediato(IM), curto(CT), médio(MD) e longo(LG) prazos
        Colunas: - cenários: menos provável(C+P), cenário normal(CN), cenário mais provável(C+P)
        compondo um arquivo json com 12 conteúdos, i.e (IM/C+P) (IM/CN) (IM/C+P) 
        (CT/C+P) (CT/CN) (CT/C+P) (MD/C+P) (MD/CN) (MD/C+P) (LG/C+P) (LG/CN) (LG/C+P)'''

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt_final}],
            response_format='json'
        )
        conteudo = response.choices[0].message.content

        print(conteudo)

    def scrape_links(links):
        """
        Função para raspar conteúdo de uma lista de links. 
        Retorna uma tupla (combined_text, bad_links):
          - combined_text: texto concatenado de todos os artigos bem-sucedidos
          - bad_links: lista de links que falharam ou retornaram texto vazio
        """
        combined_text = ""
        g = Goose()
        bad_links = []
    
        for link in links:
            try:
                article = g.extract(url=link)
                text = article.cleaned_text if article else ""
                if not text.strip():
                    # Se não houve texto, consideramos um link problemático
                    bad_links.append(link)
                    print(f"[SCRAPER] Link sem texto ou vazio: {link}")
                else:
                    combined_text += text + "\n"
            except Exception as e:
                print(f"[SCRAPER] Erro ao processar link {link}: {e}")
                bad_links.append(link)
    
        return combined_text, bad_links
