import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

###############################################
# Conteúdo originalmente em timeline_generator.py
###############################################

# Carrega as variáveis do arquivo .env
load_dotenv()

# Recupera a chave da API do arquivo .env
openai_api_key = os.getenv("OPENAI_API_KEY")

if not openai_api_key:
    raise ValueError("A chave da API não foi encontrada. Verifique o arquivo .env.")

# Inicializa o cliente OpenAI
client = OpenAI(api_key=openai_api_key)

# Prompt de instruções aprimorado (sem incluir os arquivos de parser)
prompt_instructions = """
Você está usando o modelo GPT-4. Seu objetivo é gerar um arquivo .timeline compatível com o parser da versão 2.9.0 do Timeline, 
obedecendo rigorosamente à estrutura e às regras de parsing definidas nos arquivos `timelinexml.py` e `xmlparser.py`.

1. **Início do Arquivo**  
   - O conteúdo deve iniciar estritamente com:
     <?xml version="1.0" encoding="UTF-8"?>
     <timeline>
       <version>2.9.0</version>
       <timetype>gregoriantime</timetype>

2. **Ordem dos Blocos Principais**  
   O parser define:
   - <eras> (OPCIONAL) mas, se existir, **vem** antes de <categories>
   - <categories> (SINGLE)
   - <events> (SINGLE)
   - <view> (SINGLE)
   - <now> (OPCIONAL)
   Mantenha essa ordem.  

3. **Detalhe dos Sub-elementos**  
   - **Caso `<eras>` apareça**:
     - `<era>` (ANY)
       - `<name>`, `<start>`, `<end>`, `<color>`, `<ends_today>` (opcional)
   - **`<categories>`** (SINGLE)  
     - `<category>` (ANY)
       - `<name>`, `<color>` etc.
   - **`<events>`** (SINGLE)  
     - `<event>` (ANY), com a **seguinte ordem** de sub-tags:
       1. `<start>` (SINGLE)  
       2. `<end>` (SINGLE)  
       3. `<text>` (SINGLE)  
       4. `<progress>` (OPCIONAL)  
       5. `<fuzzy>` (OPCIONAL)  
       6. `<fuzzy_start>` (OPCIONAL)  
       7. `<fuzzy_end>` (OPCIONAL)  
       8. `<locked>` (OPCIONAL)  
       9. `<ends_today>` (OPCIONAL)  
       10. `<category>` (OPCIONAL)  
       11. `<categories>` (OPCIONAL, com `<category>` ANY dentro)  
       12. `<description>` (OPCIONAL)  
       13. `<labels>` (OPCIONAL)  
       14. `<alert>` (OPCIONAL)  
       15. `<hyperlink>` (OPCIONAL)  
       16. `<icon>` (OPCIONAL)  
       17. `<default_color>` (OPCIONAL, r,g,b)  
       18. `<milestone>` (OPCIONAL)  
   - **`<view>`** (SINGLE)  
     - `<displayed_period>` (OPCIONAL)
       - `<start>`, `<end>` (SINGLE)
     - `<hidden_categories>` (OPCIONAL)
       - `<name>` (ANY)
   - **`<now>`** (OPCIONAL) (se existir, vem após `<view>`)

4. **Formato das Datas**  
   - Sempre use `YYYY-MM-DD HH:MM:SS` em `<start>` e `<end>`.

5. **Formato das Cores**  
   - Use `r,g,b` (sem #).

6. **Sem atributos**  
   - Nenhum `<tag attr="...">`.

7. **Exemplo Simplificado**  
   <?xml version="1.0" encoding="UTF-8"?>
   <timeline>
     <version>2.9.0</version>
     <timetype>gregoriantime</timetype>
     <eras>
       <era>
         <name>Exemplo</name>
         <start>2025-01-01 00:00:00</start>
         <end>2025-02-01 00:00:00</end>
         <color>200,200,200</color>
         <ends_today>False</ends_today>
       </era>
     </eras>
     <categories>
       <category>
         <name>Política</name>
         <color>255,0,0</color>
       </category>
     </categories>
     <events>
       <event>
         <start>2025-01-10 00:00:00</start>
         <end>2025-01-10 23:59:59</end>
         <text>Evento Exemplo</text>
         <progress>0</progress>
         <fuzzy>False</fuzzy>
         <locked>False</locked>
         <ends_today>False</ends_today>
         <category>Política</category>
         <default_color>255,255,0</default_color>
       </event>
     </events>
     <view>
       <displayed_period>
         <start>2025-01-01 00:00:00</start>
         <end>2025-02-01 00:00:00</end>
       </displayed_period>
     </view>
   </timeline>

**Restrições Finais**  
- Não inclua texto solto entre tags que tenham filhos.  
- Não use delimitadores de código como ``` ou '''.  
- Se quiser mais eventos ou categorias, repita mantendo a ordem exata.  
- **Não coloque nada antes de** `<?xml version="1.0" encoding="UTF-8"?>` **nem nada depois de** `</timeline>`.  
- **Use as informações em {{text_list}}** para criar os eventos, mas respeite essa hierarquia fielmente.

**Erros Comuns e Como Evitá-los**:
- **Erro de Ordem**: Certifique-se de que a ordem das tags seja respeitada. Por exemplo, `<eras>` deve vir antes de `<categories>`.
- **Erro de Formato de Data**: Use sempre o formato `YYYY-MM-DD HH:MM:SS` para datas.
- **Erro de Formato de Cor**: Use o formato `r,g,b` para cores, sem o símbolo `#`.
- **Erro de Atributos**: Não use atributos em tags. Todas as informações devem estar dentro de tags filhas.
- **Erro de Texto Solto**: Não inclua texto solto entre tags que tenham filhos.

Se o XML gerado não for válido, a função de verificação indicará o erro e reativará a API para corrigir o XML.
"""

class TimelineValidator:
    """
    Classe responsável por validar e corrigir o XML da timeline.
    """
    def __init__(self, client, prompt_instructions):
        self.client = client
        self.prompt_instructions = prompt_instructions
        self.attempts = 0  # Contador de tentativas

    def sanitize_xml(self, xml_string):
        """
        Remove qualquer conteúdo antes de <?xml version="1.0" encoding="UTF-8"?> 
        e depois de </timeline>.
        """
        start_tag = '<?xml version="1.0" encoding="UTF-8"?>'
        end_tag = '</timeline>'
        
        if start_tag in xml_string:
            xml_string = xml_string[xml_string.index(start_tag):]
        if end_tag in xml_string:
            idx_end = xml_string.index(end_tag) + len(end_tag)
            xml_string = xml_string[:idx_end]
        return xml_string

    def validate_timeline(self, timeline_xml):
        """
        Valida o XML gerado usando o parser do Timeline 2.9.0.
        Retorna uma mensagem de erro se houver problemas.
        """
        try:
            # Simulação de validação pelo Timeline 2.9.0
            root = ET.fromstring(timeline_xml)
            if root.tag != "timeline":
                return "A tag raiz deve ser <timeline>."
            
            # Verifica a ordem das tags principais
            expected_order = ["version", "timetype", "eras", "categories", "events", "view", "now"]
            current_order = [child.tag for child in root]
            
            for expected, current in zip(expected_order, current_order):
                if expected != current:
                    return f"A tag <{expected}> deve vir antes de <{current}>."
            
            # Verifica o formato das datas e cores
            for event in root.findall(".//event"):
                start = event.find("start").text
                end = event.find("end").text
                if not re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", start):
                    return f"Formato de data inválido em <start>: {start}"
                if not re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", end):
                    return f"Formato de data inválido em <end>: {end}"
                
                color = event.find("default_color")
                if color is not None:
                    if not re.match(r"\d{1,3},\d{1,3},\d{1,3}", color.text):
                        return f"Formato de cor inválido em <default_color>: {color.text}"
            
            # Se tudo estiver correto, retorna None (sem erros)
            return None
        
        except Exception as e:
            return f"Erro ao validar o XML: {e}"

    def generate_timeline(self, text_list):
        """
        Gera uma timeline a partir de uma lista de textos, validando e corrigindo o XML até que esteja correto.
        O loop é interrompido após 5 tentativas sem sucesso.
        """
        while self.attempts < 5:
            print(f"\n--- Tentativa {self.attempts + 1} ---")

            # Concatena os itens da lista em um único texto (respeitando quebras de linha)
            combined_text = "\n".join(text_list)

            # Monta o prompt final
            prompt = f"{self.prompt_instructions}\n\nConteúdo de text_list:\n{combined_text}"
            print("\n--- Prompt Enviado para a API ---")
            print(prompt)

            try:
                # Chamada à API, usando GPT-4
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}]
                )

                timeline_xml = response.choices[0].message.content
                print("\n--- Resposta da API ---")
                print(timeline_xml)

                # Aplica a função de sanitização para remover lixo antes/depois das tags
                timeline_xml = self.sanitize_xml(timeline_xml)

                # Remove BOM e espaços à esquerda que possam quebrar o XML
                timeline_xml = timeline_xml.lstrip("\ufeff").lstrip()

                # Se houver <timeline ...> com atributos, remover
                if "<timeline " in timeline_xml:
                    timeline_xml = timeline_xml.replace("<timeline ", "<timeline>")

                # Valida o XML usando o Timeline 2.9.0
                error_message = self.validate_timeline(timeline_xml)
                if error_message is None:
                    print("\n--- Timeline gerada com sucesso! ---")
                    return timeline_xml
                else:
                    print(f"\n--- Erro na validação: {error_message} ---")
                    self.attempts += 1

                    # Ativa o prompt de correção
                    correction_prompt = f"""
                    O XML gerado contém o seguinte erro: {error_message}.
                    Por favor, corrija o XML seguindo as regras fornecidas anteriormente.
                    Preserve ipsis literis, todos os conteúdos acerca dos eventos e eras apresentados,
                    em situação nenhuma remova, omita, ou diminua estes conteúdos.
                    Manipule apenas a estrutura do arquivo xml.
                    Aqui está o XML incorreto para referência:
                    {timeline_xml}
                    """
                    print("\n--- Prompt de Correção Enviado para a API ---")
                    print(correction_prompt)

                    # Reativa a API com o prompt de correção
                    response = self.client.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role": "user", "content": correction_prompt}]
                    )

                    timeline_xml = response.choices[0].message.content
                    print("\n--- Resposta da API (Correção) ---")
                    print(timeline_xml)

            except Exception as e:
                print(f"Erro ao acessar a API: {e}")
                self.attempts += 1

        print("\n--- Número máximo de tentativas atingido (5). Abortando... ---")
        return None

class TimelineGenerator:
    """
    Classe que unifica a criação de arquivos .timeline, usando o TimelineValidator.
    """
    def __init__(self):
        # Instancia o validador com o mesmo cliente e prompt do GPT-4
        self.validator = TimelineValidator(client, prompt_instructions)

    def create_timeline(self, text_list):
        """
        Recebe uma lista de strings (text_list) a serem analisadas e concatenadas
        para montagem do prompt final, preservando todo o resto da lógica.
        """
        validated_xml = self.validator.generate_timeline(text_list)
        
        if validated_xml is None:
            print("Não foi possível gerar uma timeline válida.")
            return None

        # Gera um nome de arquivo baseado na data/hora
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Verifica (e cria, se não existir) a pasta 'timeline_api_output'
        output_folder = "static/generated/timeline_output"
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        timeline_file = f"{output_folder}/{timestamp}.timeline"

        # Salva com utf-8-sig
        with open(timeline_file, 'w', encoding='utf-8-sig') as file:
            file.write(validated_xml)

        print(f"\n--- Linha do tempo salva com sucesso em: {timeline_file} ---")
        return timeline_file


###############################################
# Conteúdo originalmente em timeline_javascript.py
###############################################

# Removemos as importações e elementos específicos do Flask
# mas preservamos o parse_timeline_xml e parse_color ipsis litteris.

def parse_color(color_str):
    # Converte uma string de cor 'R,G,B' para o formato hexadecimal '#RRGGBB'
    r, g, b = map(int, color_str.split(','))
    return f'#{r:02x}{g:02x}{b:02x}'

class TimelineParser:
    """
    Classe responsável por carregar e interpretar um arquivo .timeline (XML) 
    de acordo com a lógica original do timeline_javascript.py.
    """
    def __init__(self):
        pass

    def parse_timeline_xml(self, file_path):
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Captura minimalista de versão e tipo de tempo do XML,
        # preservando todas as demais partes do código.
        version_node = root.find('version')
        timetype_node = root.find('timetype')
        version = version_node.text if version_node is not None else "2.9.0"
        timetype = timetype_node.text if timetype_node is not None else "gregoriantime"

        # Parse categories
        categories_elem = root.find('categories')
        categories = {}
        if categories_elem is not None:
            for category in categories_elem:
                name = category.find('name').text
                color = parse_color(category.find('color').text)
                progress_color = (parse_color(category.find('progress_color').text) 
                                  if category.find('progress_color') is not None else None)
                done_color = (parse_color(category.find('done_color').text) 
                              if category.find('done_color') is not None else None)
                font_color = (parse_color(category.find('font_color').text) 
                              if category.find('font_color') is not None and category.find('font_color').text is not None 
                              else None)

                categories[name] = {
                    'color': color,
                    'progress_color': progress_color,
                    'done_color': done_color,
                    'font_color': font_color
                }

        # Parse eras
        eras_elem = root.find('eras')
        eras = []
        if eras_elem is not None:
            for era in eras_elem:
                name = era.find('name').text
                start = era.find('start').text
                end = era.find('end').text
                color = parse_color(era.find('color').text)
                eras.append({
                    'name': name,
                    'start': start,
                    'end': end,
                    'color': color
                })

        # Parse events
        events_elem = root.find('events')
        events = []
        if events_elem is not None:
            for event in events_elem:
                start = event.find('start').text
                end = event.find('end').text
                text = event.find('text').text
                category = event.find('category').text if event.find('category') is not None else 'Uncategorized'
                description = event.find('description').text if event.find('description') is not None else ''
                default_color = (parse_color(event.find('default_color').text) 
                                 if event.find('default_color') is not None 
                                 else categories.get(category, {}).get('color', '#000000'))
                milestone = (event.find('milestone').text.lower() == 'true' 
                             if event.find('milestone') is not None else False)

                events.append({
                    'start': start,
                    'end': end,
                    'text': text,
                    'category': category,
                    'description': description,
                    'color': default_color,
                    'milestone': milestone
                })

        # Adiciona um campo de intervalo de tempo relativo (já existente)
        for ev in events:
            start_time = ev['start']
            end_time = ev['end']
            ev['duration'] = f"{start_time} to {end_time}"

        # Parse view
        view_elem = root.find('view')
        view = {}
        if view_elem is not None:
            displayed_period = view_elem.find('displayed_period')
            if displayed_period is not None:
                view = {
                    'start': displayed_period.find('start').text,
                    'end': displayed_period.find('end').text
                }

        return {
            'version': version,
            'timetype': timetype,
            'categories': categories,
            'eras': eras,
            'events': events,
            'view': view
        }
