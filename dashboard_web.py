import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import requests
from datetime import datetime
import pytz

# Endereços e portas de conexão
IP_ADDRESS = "172.171.242.134"
PORT_STH = 8666
DASH_HOST = "localhost"  # Altere para "0.0.0.0" se quiser acesso de fora da máquina

# Função para buscar dados de um atributo específico (luminosidade, temperatura ou umidade)
def get_data(attr, lastN):
    url = f"http://{IP_ADDRESS}:{PORT_STH}/STH/v1/contextEntities/type/Lamp/id/urn:ngsi-ld:Lamp:030/attributes/{attr}?lastN={lastN}"
    headers = {
        'fiware-service': 'smart',
        'fiware-servicepath': '/'
    }
    response = requests.get(url, headers=headers)
    
    print(f"URL: {url}")
    print(f"Status: {response.status_code}")
    print(f"Resposta da API: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        try:
            values = data['contextResponses'][0]['contextElement']['attributes'][0]['values']
            return values
        except KeyError as e:
            print(f"Key error: {e}")
            return []
    else:
        print(f"Erro ao acessar {url}: {response.status_code}")
        return []

# Função para converter timestamps de UTC para o horário de Brasília
def convert_to_brasilia_time(timestamps):
    utc = pytz.utc
    brasilia = pytz.timezone('America/Sao_Paulo')
    converted = []
    for t in timestamps:
        t = t.replace('T', ' ').replace('Z', '')
        try:
            dt = datetime.strptime(t, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            dt = datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
        converted.append(utc.localize(dt).astimezone(brasilia))
    return converted

# Inicializa o aplicativo Dash
app = dash.Dash(__name__)

# Define o layout da página
app.layout = html.Div([
    html.H1(
        'Dashboard de Sensores FIWARE',
        style={
            'font-family': 'Arial, sans-serif',
            'color': 'lightblue',
            'text-shadow': '1px 1px 2px black',
            'text-align': 'center',
            'margin-top': '40px',
        }
    ),
    dcc.Graph(id='graph-luminosity'),    # Gráfico da luminosidade
    dcc.Graph(id='graph-temperature'),   # Gráfico da temperatura
    dcc.Graph(id='graph-humidity'),       # Gráfico da umidade

    dcc.Store(id='data-store', data={     # Armazena os dados localmente no navegador
        'timestamps': [],
        'luminosity': [],
        'temperature': [],
        'humidity': []
    }),

    dcc.Interval(                        # Atualiza os dados a cada 2 segundos
        id='interval',
        interval=2 * 1000,
        n_intervals=0
    )
])

# Callback para atualizar os dados periodicamente
@app.callback(
    Output('data-store', 'data'),
    Input('interval', 'n_intervals'),
    State('data-store', 'data')
)
def update_data(n, stored_data):
    lastN = 30  # Quantidade de registros a buscar
    lum_data = get_data('luminosity', lastN)
    temp_data = get_data('temperature', lastN)
    hum_data = get_data('humidity', lastN)

    if lum_data and temp_data and hum_data:
        timestamps = [entry['recvTime'] for entry in lum_data]
        timestamps = convert_to_brasilia_time(timestamps)

        stored_data['timestamps'] = timestamps
        stored_data['luminosity'] = [float(entry['attrValue']) for entry in lum_data]
        stored_data['temperature'] = [float(entry['attrValue']) for entry in temp_data]
        stored_data['humidity'] = [float(entry['attrValue']) for entry in hum_data]

    return stored_data

# Callback para atualizar os gráficos com os dados armazenados
@app.callback(
    Output('graph-luminosity', 'figure'),
    Output('graph-temperature', 'figure'),
    Output('graph-humidity', 'figure'),
    Input('data-store', 'data')
)
def update_graphs(data):
    def create_graph(y_data, title, color, ylabel):
        if not data['timestamps'] or not y_data:
            return go.Figure()
        
        # Mostra o valor mais recente no título
        latest_value = y_data[-1] if y_data else 0
        title_with_value = f'{title} ({latest_value} {ylabel})'

        # Calcula a média dos valores
        mean_value = sum(y_data) / len(y_data)

        # Cria o gráfico principal
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data['timestamps'],
            y=y_data,
            mode='lines+markers',
            name=title,
            line=dict(color=color)
        ))
        # Adiciona linha horizontal representando a média
        fig.add_trace(go.Scatter(
            x=[data['timestamps'][0], data['timestamps'][-1]],
            y=[mean_value, mean_value],
            mode='lines',
            name='Média',
            line=dict(color='blue', dash='dash')
        ))

        # Configura o layout do gráfico
        fig.update_layout(
            title=title_with_value,
            xaxis_title='Tempo',
            yaxis_title=ylabel,
            yaxis=dict(range=[0, 100]),
            hovermode='closest'
        )
        return fig

    return (
        create_graph(data['luminosity'], 'Luminosidade 💡', 'orange', '%'),
        create_graph(data['temperature'], 'Temperatura 🌡', 'red', '°C'),
        create_graph(data['humidity'], 'Umidade 💧', 'green', '%')
    )

# Roda o aplicativo
if __name__ == '__main__':
    app.run(debug=True, host=DASH_HOST, port=8050)
