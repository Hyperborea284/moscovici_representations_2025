import xml.etree.ElementTree as ET
from flask import Flask, render_template, jsonify

app = Flask(__name__)

def parse_color(color_str):
    # Converte uma string de cor 'R,G,B' para o formato hexadecimal '#RRGGBB'
    r, g, b = map(int, color_str.split(','))
    return f'#{r:02x}{g:02x}{b:02x}'

def parse_timeline_xml(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Captura minimalista de versão e tipo de tempo do XML,
    # preservando todas as demais partes do código.
    version_node = root.find('version')
    timetype_node = root.find('timetype')
    version = version_node.text if version_node is not None else "2.9.0"
    timetype = timetype_node.text if timetype_node is not None else "gregoriantime"

    # Parse categories
    categories = {}
    for category in root.find('categories'):
        name = category.find('name').text
        color = parse_color(category.find('color').text)
        progress_color = parse_color(category.find('progress_color').text) if category.find('progress_color') is not None else None
        done_color = parse_color(category.find('done_color').text) if category.find('done_color') is not None else None
        font_color = parse_color(category.find('font_color').text) if category.find('font_color') is not None and category.find('font_color').text is not None else None
        # Caso haja novas tags dentro de <categories>, adicione aqui minimalmente:
        # extra_info = category.find('extra_info').text if category.find('extra_info') is not None else ''

        categories[name] = {
            'color': color,
            'progress_color': progress_color,
            'done_color': done_color,
            'font_color': font_color
            # 'extra_info': extra_info  # Exemplo se houver
        }

    # Parse eras
    eras = []
    for era in root.find('eras'):
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
    events = []
    for event in root.find('events'):
        start = event.find('start').text
        end = event.find('end').text
        text = event.find('text').text
        category = event.find('category').text if event.find('category') is not None else 'Uncategorized'
        description = event.find('description').text if event.find('description') is not None else ''
        default_color = parse_color(event.find('default_color').text) if event.find('default_color') is not None else categories.get(category, {}).get('color', '#000000')
        milestone = event.find('milestone').text.lower() == 'true' if event.find('milestone') is not None else False
        # Se existirem outros elementos no XML, adicione de forma minimalista:
        # extra_field = event.find('extra_field').text if event.find('extra_field') is not None else ''

        events.append({
            'start': start,
            'end': end,
            'text': text,
            'category': category,
            'description': description,
            'color': default_color,
            'milestone': milestone
            # 'extra_field': extra_field  # Exemplo se houver
        })

    # Adiciona um campo de intervalo de tempo relativo (já existente)
    for event in events:
        start_time = event['start']
        end_time = event['end']
        event['duration'] = f"{start_time} to {end_time}"

    # Parse view
    view = {}
    displayed_period = root.find('view/displayed_period')
    if displayed_period is not None:
        view = {
            'start': displayed_period.find('start').text,
            'end': displayed_period.find('end').text
        }

    return {
        # Adiciona versão e timetype ao dicionário para uso dinâmico
        'version': version,
        'timetype': timetype,
        'categories': categories,
        'eras': eras,
        'events': events,
        'view': view
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/timeline_data')
def timeline_data():
    # Garante a leitura correta do arquivo XML
    data = parse_timeline_xml('timeline.xml')
    return jsonify(data)

if __name__ == '__main__':
    # Habilita o modo debug para facilitar o desenvolvimento
    app.run(debug=True)
