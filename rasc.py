Em todas as correções, siga estritamente estas regras:

1)Altere minimanente os scripts, sempre garantindo a convergência entre estes 
e preservando todas as funcionalidades presentes.

2)Em absolutamente nenhuma situação remova, retire, omita, apague trechos, 
funções seções, ou remova características e funcionalidades. Caso seja necessário 
anuncie antes de proceder com as alterações.

3) Em absolutamente nenhuma situação retorne o código através do mecanismo de lousa, 
use o sistema antigo para facilitar.


Temos esta aplicaçao flask a qual faz dois serviços de analise de conteudo. 
Ambas as analises recebem texto na forma de arquivo ou inserçao no campo, 
a parte da ingestao de texto e compartilhada pelas duas aplicaçoes.

A aplicação de análise das representações sociais funciona perfeitamente, 
em nenhuma situação altere qualquer coisa dentro desta, à não ser que seja
para preservar as funcionalidades desta.

Os campos no html e a estrutura da aplicaçao estão corretos, só altere se 
for explicitamente pedido. 

Existem erros na parte de análise de sentimentos, especificamente: 

1) Esta gera uma análise do texto onde são indexados as frases, parágrafos, 
é feita uma contagem e é anunciado uma timestamp. Esta parte do html deve ser 
processada cada vez que o usuário ativa o botão 'Enviar Conteúdo' após incluir o texto. 
Nesta situação, estes três campos deveriam estar sendo preenchidos com os conteúdos processados: 
'Texto Analisado', 'Data e Hora da Análise' e 'Número de Parágrafos e Frases'. 
Estas informações devem substituir o campo de ingestão de texto até que o botão 'Enviar outro conteúdo' 
seja ativado, esta última operação está funcionando corretamente. Analise as operações envolvendo a 
geração dos conteúdos destes campos e como estes estão sendo montados para apresentar 
os centeúdos ao usuário. 

2) O script de análise de sentimentos usa de um mecanismo de machine learning para gerar gráficos diversos. 
Estes não estão sendo encontrados pelo servidor e deveriam compor o conteúdo da aba 'Análise de sentimentos'. 
Reveja as ativações, perceba se estes estão sendo gerados, onde estão sendo salvos e como estão sendo servidos.




O erro mais recente, e os arquivos na versão atual:






Extraindo palavras do documento...
127.0.0.1 - - [31/Dec/2024 16:01:48] "POST /select_algorithm_and_generate HTTP/1.1" 200 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "POST /process_sentiment HTTP/1.1" 200 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/pie_chart_20241231_160145.png HTTP/1.1" 200 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/bar_chart_20241231_160145.png HTTP/1.1" 200 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/raiva_score_20241231_160145.png HTTP/1.1" 200 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/raiva_distribution_20241231_160145.png HTTP/1.1" 404 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/tristeza_score_20241231_160145.png HTTP/1.1" 200 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/tristeza_distribution_20241231_160145.png HTTP/1.1" 404 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/surpresa_distribution_20241231_160145.png HTTP/1.1" 404 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/surpresa_score_20241231_160145.png HTTP/1.1" 200 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/medo_distribution_20241231_160145.png HTTP/1.1" 404 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/medo_score_20241231_160145.png HTTP/1.1" 200 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/desgosto_distribution_20241231_160145.png HTTP/1.1" 404 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/desgosto_score_20241231_160145.png HTTP/1.1" 200 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/alegria_distribution_20241231_160145.png HTTP/1.1" 404 -
127.0.0.1 - - [31/Dec/2024 16:01:48] "GET /static/generated/alegria_score_20241231_160145.png HTTP/1.1" 200 -





    def plot_individual_emotion_charts(self, scores_list: list, paragraph_end_indices: list, timestamp: str):
        """Plota gráficos de linhas individuais para cada sentimento e decide qual distribuição estatística é mais adequada.
    
        Args:
            scores_list (list): Lista de pontuações de emoções.
            paragraph_end_indices (list): Lista indicando fim dos parágrafos.
            timestamp (str): Carimbo de data/hora para nomear os arquivos salvos.
        """
        print("Plotando gráficos de linhas individuais para cada emoção...")
        emotions = list(self.emotions_funcs.keys())
    
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
    
            # Salvando a imagem de pontuação para cada emoção
            emotion_image_path = self.generated_images_dir / f'{emotion}_score_{timestamp}.png'
            plt.savefig(emotion_image_path)
            plt.close()
    
            # Analisando os dados e gerando o gráfico de distribuição mais adequado
            emotion_scores = [score[i] for score in scores_list]
            nature = analyze_data(emotion_scores)  # Identificação da característica da distribuição
            outliers, lower_bound, upper_bound = detect_outliers(emotion_scores)  # Detecção de outliers
            
            # Incluindo o caminho de salvamento correto para o gráfico de distribuição
            distribution_image_path = self.generated_images_dir / f'{emotion}_distribution_{timestamp}.png'
            plot_distribution(emotion_scores, f'{emotion} ({nature})', outliers, lower_bound, upper_bound, distribution_image_path)



    Altere o html para que exista um espaço dinâmico entre cada imagem e faça com que estas sejam proporcianais 
    ao tamalho da visualização, alterando so tamanhos dos elementos dinâmicamente. Preserve absolutamente todas 
    as outras caarcterísticas.



































preserve:
SentimentAnalyzer 
reset_analyzer
deactivate_analyzer
count_paragraphs
count_sentences
is_valid_html
process_document
process_text
analyze_paragraphs
aplicastemmer
buscapalavras
buscafrequencia
buscapalavrasunicas
extratorpalavras
classify_emotion
plot_individual_emotion_charts
plot_pie_chart
plot_bar_chart
execute_analysis_text

altere 
generate_html_content
generate_html_content_process
