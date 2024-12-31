import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm, kurtosis, skew, shapiro
import seaborn as sns

# Função para analisar os dados e determinar a natureza predominante
def analyze_data(data):
    kurt = kurtosis(data, fisher=False)
    skewness = skew(data)

    if kurt > 3 and skewness > 0:
        return "Leptocúrtica com Concentração em Sigmas Positivos"
    elif kurt > 3 and skewness < 0:
        return "Leptocúrtica com Concentração em Sigmas Negativos"
    elif kurt > 3:
        return "Leptocúrtica Neutra"
    elif kurt < 3 and skewness > 0:
        return "Platocúrtica com Concentração em Sigmas Positivos"
    elif kurt < 3 and skewness < 0:
        return "Platocúrtica com Concentração em Sigmas Negativos"
    else:
        return "Platocúrtica Neutra"

# Função para identificar outliers usando o método do intervalo interquartil (IQR)
def detect_outliers(data):
    # Converte data para um array NumPy caso ainda não seja
    data = np.asarray(data)  # Assegura que `data` é um array NumPy
    q1 = np.percentile(data, 25)
    q3 = np.percentile(data, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    # Corrige a operação de filtragem usando máscaras booleanas NumPy
    outliers = data[(data < lower_bound) | (data > upper_bound)]
    return outliers, lower_bound, upper_bound

# Função para normalizar os dados centrando em torno da média
def normalize_to_center(data):
    """
    Normaliza os dados de forma que os valores se distribuam em torno da média.

    Args:
        data (list or np.array): Lista ou array de dados numéricos a serem normalizados.

    Returns:
        np.array: Dados normalizados centrados na média.
    """
    data = np.array(data)
    mean = np.mean(data)  # Calcula a média dos dados
    centered_data = data - mean  # Centraliza os dados
    max_abs = np.max(np.abs(centered_data))  # Encontra o máximo absoluto para normalizar
    if max_abs == 0:
        return centered_data  # Retorna os dados sem normalizar se max_abs for zero
    return centered_data / max_abs  # Normaliza para o intervalo [-1, 1] centrado na média

# Função para calcular e plotar a distribuição normal e a curtose para cada conjunto de dados
def plot_distribution(data, title, outliers, lower_bound, upper_bound, save_path):
    """Plota a distribuição dos dados, destacando a natureza e salvando o gráfico."""
    # Normaliza os dados antes de ploteá-los
    normalized_data = normalize_to_center(data)
    mean = np.mean(normalized_data)
    std_dev = np.std(normalized_data)
    x = np.linspace(min(normalized_data), max(normalized_data), 1000)
    y = norm.pdf(x, mean, std_dev)

    plt.figure(figsize=(12, 8))
    plt.hist(normalized_data, bins=30, density=True, alpha=0.6, color='g', label='Dados Normalizados')
    plt.plot(x, y, label='Distribuição Normal', color='darkred')

    sns.kdeplot(normalized_data, color='blue', label='Estimativa de Densidade de Kernel', linestyle='--')

    for i in range(1, 4):
        plt.axvline(mean - i*std_dev, color='black', linestyle='dashed', linewidth=1)
        plt.axvline(mean + i*std_dev, color='black', linestyle='dashed', linewidth=1)

    plt.axhline(0, color='black', linestyle='dotted', linewidth=1)
    plt.axvline(lower_bound, color='orange', linestyle='dotted', linewidth=1, label='Limite Inferior (Outliers)')
    plt.axvline(upper_bound, color='orange', linestyle='dotted', linewidth=1, label='Limite Superior (Outliers)')

    plt.scatter(outliers, [0] * len(outliers), color='red', label='Outliers', zorder=5)

    plt.text(mean, max(y)*0.5, r'$\mu$', horizontalalignment='center', fontsize=12)
    plt.text(mean - std_dev, max(y)*0.2, r'$\mu - 1\sigma$', horizontalalignment='center', fontsize=12)
    plt.text(mean + std_dev, max(y)*0.2, r'$\mu + 1\sigma$', horizontalalignment='center', fontsize=12)
    plt.text(mean - 2*std_dev, max(y)*0.05, r'$\mu - 2\sigma$', horizontalalignment='center', fontsize=12)
    plt.text(mean + 2*std_dev, max(y)*0.05, r'$\mu + 2\sigma$', horizontalalignment='center', fontsize=12)
    plt.text(mean - 3*std_dev, max(y)*0.01, r'$\mu - 3\sigma$', horizontalalignment='center', fontsize=12)
    plt.text(mean + 3*std_dev, max(y)*0.01, r'$\mu + 3\sigma$', horizontalalignment='center', fontsize=12)

    kurt = kurtosis(normalized_data, fisher=False)
    skewness = skew(normalized_data)
    _, p_value = shapiro(normalized_data)

    plt.title(f'{title}\nCurtose: {kurt:.2f}, Assimetria: {skewness:.2f}, p-valor do Shapiro-Wilk: {p_value:.4f}')
    plt.xlabel('Valor')
    plt.ylabel('Densidade de Probabilidade')
    plt.legend()
    plt.tight_layout()
    plt.savefig(save_path)  # Salva o gráfico no caminho especificado
    plt.close()
