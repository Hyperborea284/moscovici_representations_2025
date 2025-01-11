import requests
from goose3 import Goose

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
