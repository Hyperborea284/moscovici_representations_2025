from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
import time

def buscar_twitter(termo_busca, num_resultados=10):
    """
    Busca comentários no Twitter usando Selenium e retorna os data points necessários.

    Args:
        termo_busca (str): Termo a ser pesquisado no Twitter.
        num_resultados (int): Número de comentários a coletar.

    Returns:
        List[dict]: Lista de dicionários com os dados coletados.
    """
    # Configurar o perfil do Firefox
    options = Options()
    options.add_argument("-profile")
    options.add_argument("/home/base/snap/firefox/common/.mozilla/firefox/3v6mb1xy.Eudaimonia") 

    # Configurar o serviço do geckodriver
    service = Service("/usr/bin/geckodriver")  # Caminho para o geckodriver

    # Iniciar o navegador
    driver = webdriver.Firefox(service=service, options=options)
    driver.get("https://twitter.com/explore")

    # Aguardar o carregamento
    time.sleep(5)

    # Localizar a barra de busca
    search_box = driver.find_element(By.XPATH, '//input[@aria-label="Search query"]')
    search_box.send_keys(termo_busca)
    search_box.send_keys(Keys.RETURN)

    # Aguardar os resultados carregarem
    time.sleep(5)

    # Coletar tweets
    comentarios = []
    tweets = driver.find_elements(By.XPATH, '//article[@data-testid="tweet"]')

    for tweet in tweets[:num_resultados]:
        try:
            autor = tweet.find_element(By.XPATH, './/div[@role="button"]/span').text
            conteudo = tweet.find_element(By.XPATH, './/div[2]/div[2]/div[1]').text
            timestamp = tweet.find_element(By.XPATH, './/time').get_attribute('datetime')
            localizacao = "Desconhecida"  # Twitter não fornece localização por padrão, mas você pode inferir com APIs de geolocalização
            likes = tweet.find_element(By.XPATH, './/div[@data-testid="like"]').text or "0"
            retweets = tweet.find_element(By.XPATH, './/div[@data-testid="retweet"]').text or "0"
            comentarios.append({
                "autor": autor,
                "conteudo": conteudo,
                "timestamp": timestamp,
                "localizacao": localizacao,
                "likes": int(likes.replace(",", "")),
                "retweets": int(retweets.replace(",", ""))
            })
        except Exception as e:
            print(f"Erro ao processar tweet: {e}")

    # Fechar o navegador
    driver.quit()

    return comentarios


# Exemplo de uso
if __name__ == "__main__":
    termo = "inteligência artificial"
    resultados = buscar_twitter(termo, num_resultados=5)
    for idx, res in enumerate(resultados, start=1):
        print(f"Tweet {idx}: {res}")
